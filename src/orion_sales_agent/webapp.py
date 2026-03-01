from __future__ import annotations
"""FastAPI web layer for OrionPulse.

Provides typed API endpoints, token-role access control, response envelope
standardization, and a lightweight built-in HTML chat UI.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .agent import OrionAgent
from .analytics import forecast_metric, kpi_summary
from .api_models import (
    AskEnvelope,
    AskWithAnalyticsExportsEnvelope,
    AskWithVisualsEnvelope,
    ChatEnvelope,
    ChatPayload,
    ForecastEnvelope,
    KpiEnvelope,
)
from .auth import require_role
from .config import settings, validate_auth_configuration


def _startup_auth_guard() -> None:
    """Validate auth posture during app startup."""

    validate_auth_configuration(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan hook used for startup auth validation."""

    _startup_auth_guard()
    yield


app = FastAPI(title="OrionPulse Agent UI", lifespan=lifespan)
agent = OrionAgent()
app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")
app.mount("/specs", StaticFiles(directory="specs"), name="specs")
HOME_TEMPLATE = Path(__file__).resolve().parent / "templates" / "home.html"


def _response_envelope(
    data,
    warnings: list[str] | None = None,
    execution_mode: str | None = None,
    fallback_reason: str | None = None,
) -> dict:
    """Build the standard JSON envelope with optional provenance fields."""

    payload = {
        "status": "ok",
        "trace_id": f"orion-{uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "warnings": warnings or [],
        "data": data,
    }
    if execution_mode:
        payload["execution_mode"] = execution_mode
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    return payload


def _effective_web_mode() -> str:
    """Resolve configured web execution mode with safe fallback to `auto`."""

    mode = settings.web_default_mode.strip().lower()
    if mode not in {"auto", "deterministic", "llm"}:
        return "auto"
    return mode


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    """Serve chat UI HTML from external template file."""

    return HOME_TEMPLATE.read_text(encoding="utf-8")


def _chat_impl(payload: ChatPayload, x_orion_token: str | None):
    """Shared implementation for chat endpoints and versioned aliases."""

    require_role(x_orion_token, "analyst")

    q = payload.q.strip()
    with_visuals = payload.with_visuals
    with_analytics = payload.with_analytics
    fmt = payload.fmt

    resp = agent.answer(q, mode=_effective_web_mode())
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
    }

    if with_visuals:
        from .visualization import generate_insight_pack

        vfmt = fmt if fmt in {"png", "svg"} else "png"
        result["visuals"] = generate_insight_pack(q, fmt=vfmt)
    if with_analytics:
        require_role(x_orion_token, "admin")
        from .analytics_exports import export_analytics_pack

        bfmt = fmt if fmt in {"csv", "parquet"} else "csv"
        result["analytics_exports"] = export_analytics_pack(fmt=bfmt)
    return _response_envelope(result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason)


@app.post("/chat", response_model=ChatEnvelope)
def chat(payload: ChatPayload, x_orion_token: str | None = Header(default=None)) -> ChatEnvelope:
    return _chat_impl(payload, x_orion_token)


@app.post("/v1/chat", response_model=ChatEnvelope)
def chat_v1(payload: ChatPayload, x_orion_token: str | None = Header(default=None)) -> ChatEnvelope:
    return _chat_impl(payload, x_orion_token)


def _kpi_impl(x_orion_token: str | None) -> dict:
    """Shared implementation for KPI endpoints."""

    require_role(x_orion_token, "analyst")
    return _response_envelope(kpi_summary(settings.db_path), execution_mode="deterministic")


@app.get("/kpi", response_model=KpiEnvelope)
def kpi(x_orion_token: str | None = Header(default=None)) -> KpiEnvelope:
    return _kpi_impl(x_orion_token)


@app.get("/v1/kpi", response_model=KpiEnvelope)
def kpi_v1(x_orion_token: str | None = Header(default=None)) -> KpiEnvelope:
    return _kpi_impl(x_orion_token)


def _forecast_impl(x_orion_token: str | None) -> dict:
    """Shared implementation for forecast endpoints."""

    require_role(x_orion_token, "analyst")
    out = forecast_metric(settings.db_path)
    warnings: list[str] = []
    if out.get("warning"):
        warnings.append(str(out.get("warning")))
    return _response_envelope(out, warnings=warnings, execution_mode="deterministic")


@app.get("/forecast", response_model=ForecastEnvelope)
def forecast(x_orion_token: str | None = Header(default=None)) -> ForecastEnvelope:
    return _forecast_impl(x_orion_token)


@app.get("/v1/forecast", response_model=ForecastEnvelope)
def forecast_v1(x_orion_token: str | None = Header(default=None)) -> ForecastEnvelope:
    return _forecast_impl(x_orion_token)


def _ask_impl(q: str, x_orion_token: str | None) -> dict:
    """Shared implementation for ask endpoints."""

    require_role(x_orion_token, "analyst")
    resp = agent.answer(q, mode=_effective_web_mode())
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
    }
    return _response_envelope(result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason)


@app.get("/ask", response_model=AskEnvelope)
def ask(q: str = Query(..., min_length=3, max_length=400), x_orion_token: str | None = Header(default=None)):
    return _ask_impl(q, x_orion_token)


@app.get("/v1/ask", response_model=AskEnvelope)
def ask_v1(q: str = Query(..., min_length=3, max_length=400), x_orion_token: str | None = Header(default=None)):
    return _ask_impl(q, x_orion_token)


def _ask_with_visuals_impl(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("png"),
    x_orion_token: str | None = None,
):
    """Shared implementation for ask-with-visuals endpoints."""

    require_role(x_orion_token, "analyst")
    from .visualization import generate_insight_pack

    resp = agent.answer(q, mode=_effective_web_mode())
    visuals = generate_insight_pack(q, fmt=fmt)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
        "visuals": visuals,
        "artifacts_base": "/artifacts/charts",
    }
    return _response_envelope(result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason)


@app.get("/ask_with_visuals", response_model=AskWithVisualsEnvelope)
def ask_with_visuals(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("png"),
    x_orion_token: str | None = Header(default=None),
):
    return _ask_with_visuals_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


@app.get("/v1/ask_with_visuals", response_model=AskWithVisualsEnvelope)
def ask_with_visuals_v1(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("png"),
    x_orion_token: str | None = Header(default=None),
):
    return _ask_with_visuals_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


def _ask_with_analytics_exports_impl(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("csv"),
    x_orion_token: str | None = None,
):
    """Shared implementation for admin-only Analytics Exports endpoint."""

    require_role(x_orion_token, "admin")
    from .analytics_exports import export_analytics_pack

    resp = agent.answer(q, mode="deterministic")
    analytics_pack = export_analytics_pack(fmt=fmt)
    result = {
        "intent": resp.intent,
        "answer": resp.answer,
        "reasoning_summary": resp.reasoning_summary,
        "data": resp.data,
        "followups": resp.followups,
        "analytics_exports": analytics_pack,
        "artifacts_base": "/artifacts/analytics_exports",
        "semantic_specs_base": "/specs/analytics_exports",
    }
    return _response_envelope(result, execution_mode="deterministic")


@app.get("/ask_with_analytics_exports", response_model=AskWithAnalyticsExportsEnvelope)
def ask_with_analytics_exports(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("csv"),
    x_orion_token: str | None = Header(default=None),
):
    return _ask_with_analytics_exports_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


@app.get("/v1/ask_with_analytics_exports", response_model=AskWithAnalyticsExportsEnvelope)
def ask_with_analytics_exports_v1(
    q: str = Query(..., min_length=3, max_length=400),
    fmt: str = Query("csv"),
    x_orion_token: str | None = Header(default=None),
):
    return _ask_with_analytics_exports_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)
