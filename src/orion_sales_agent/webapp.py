"""FastAPI web layer for OrionPulse.

Provides typed API endpoints, token-role access control, response envelope
standardization, and a lightweight built-in HTML chat UI.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
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
    HealthEnvelope,
    KpiEnvelope,
)
from .auth import require_role
from .config import settings, validate_auth_configuration

# ---------------------------------------------------------------------------
# Token-bucket rate limiter (stdlib only — no extra deps)
# ---------------------------------------------------------------------------
# Allows up to RATE_LIMIT_REQUESTS requests per RATE_LIMIT_WINDOW_SECONDS
# per client IP.  Uses a deque of timestamps — O(1) amortised per request.
_RATE_LIMIT_REQUESTS: int = 30
_RATE_LIMIT_WINDOW_SECONDS: float = 60.0
_rate_buckets: dict[str, deque] = {}
_rate_lock = threading.Lock()

# How often (in requests) to sweep _rate_buckets for fully-drained entries.
# Prevents unbounded memory growth when many unique IPs are seen over time.
_RATE_BUCKET_SWEEP_INTERVAL: int = 500
_rate_request_counter: int = 0


def _client_ip(request: Request) -> str:
    """Extract the real client IP, respecting common reverse-proxy headers.

    Checks ``X-Forwarded-For`` (first entry) then ``X-Real-IP`` before
    falling back to the direct connection address.  This ensures the rate
    limiter works correctly behind nginx, CloudFront, or any load balancer.
    """
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(client_ip: str) -> None:
    """Raise HTTP 429 if *client_ip* exceeds the request rate limit.

    Thread-safe via a module-level lock; does not require any external
    dependency beyond stdlib.  Periodically sweeps empty buckets to prevent
    unbounded memory growth when many unique IPs are seen over a long uptime.
    """
    global _rate_request_counter
    now = time.monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    with _rate_lock:
        if client_ip not in _rate_buckets:
            _rate_buckets[client_ip] = deque()
        bucket = _rate_buckets[client_ip]
        # Evict timestamps outside the window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= _RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded: max {_RATE_LIMIT_REQUESTS} requests "
                    f"per {int(_RATE_LIMIT_WINDOW_SECONDS)}s"
                ),
            )
        bucket.append(now)
        # Periodic sweep: remove buckets whose windows have fully expired so
        # the dict does not grow without bound across many unique source IPs.
        _rate_request_counter += 1
        if _rate_request_counter % _RATE_BUCKET_SWEEP_INTERVAL == 0:
            stale = [ip for ip, b in _rate_buckets.items() if not b]
            for ip in stale:
                del _rate_buckets[ip]


def _startup_auth_guard() -> None:
    """Validate auth posture during app startup."""

    validate_auth_configuration(settings)


def _ensure_static_dirs() -> None:
    """Create static mount directories if they do not exist."""

    Path("artifacts").mkdir(parents=True, exist_ok=True)
    Path("specs").mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan hook used for startup auth validation."""

    _ensure_static_dirs()
    _startup_auth_guard()
    yield


_ensure_static_dirs()
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
        "timestamp": datetime.now(UTC).isoformat(),
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


@app.get("/health", response_model=HealthEnvelope)
def health() -> dict:
    """Liveness probe — returns service version and uptime timestamp.

    No authentication required so load-balancers and container orchestrators
    can call it freely.
    """
    return {
        "status": "ok",
        "trace_id": f"orion-{uuid4().hex[:12]}",
        "timestamp": datetime.now(UTC).isoformat(),
        "warnings": [],
        "data": {
            "service": "orionpulse-data-agent",
            "version": "1.1.0",
            "db_path": str(settings.db_path),
            "llm_enabled": bool(settings.llm_api_key.strip()),
        },
    }


def _chat_impl(payload: ChatPayload, x_orion_token: str | None) -> dict:
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

    if with_visuals and resp.intent != "general":
        from .visualization import generate_insight_pack

        vfmt = fmt if fmt in {"png", "svg"} else "png"
        result["visuals"] = generate_insight_pack(q, fmt=vfmt)
    if with_analytics:
        require_role(x_orion_token, "admin")
        from .analytics_exports import export_analytics_pack

        bfmt = fmt if fmt in {"csv", "parquet"} else "csv"
        result["analytics_exports"] = export_analytics_pack(fmt=bfmt)
    return _response_envelope(
        result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason
    )


@app.post("/chat", response_model=ChatEnvelope)
def chat(
    payload: ChatPayload,
    request: Request,
    x_orion_token: str | None = Header(default=None),
) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    return _chat_impl(payload, x_orion_token)


@app.post("/v1/chat", response_model=ChatEnvelope)
def chat_v1(
    payload: ChatPayload,
    request: Request,
    x_orion_token: str | None = Header(default=None),
) -> dict:
    _check_rate_limit(request.client.host if request.client else "unknown")
    return _chat_impl(payload, x_orion_token)


def _kpi_impl(x_orion_token: str | None) -> dict:
    """Shared implementation for KPI endpoints."""

    require_role(x_orion_token, "analyst")
    return _response_envelope(kpi_summary(settings.db_path), execution_mode="deterministic")


@app.get("/kpi", response_model=KpiEnvelope)
def kpi(request: Request, x_orion_token: str | None = Header(default=None)) -> dict:
    _check_rate_limit(_client_ip(request))
    return _kpi_impl(x_orion_token)


@app.get("/v1/kpi", response_model=KpiEnvelope)
def kpi_v1(request: Request, x_orion_token: str | None = Header(default=None)) -> dict:
    _check_rate_limit(_client_ip(request))
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
def forecast(request: Request, x_orion_token: str | None = Header(default=None)) -> dict:
    _check_rate_limit(_client_ip(request))
    return _forecast_impl(x_orion_token)


@app.get("/v1/forecast", response_model=ForecastEnvelope)
def forecast_v1(request: Request, x_orion_token: str | None = Header(default=None)) -> dict:
    _check_rate_limit(_client_ip(request))
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
    return _response_envelope(
        result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason
    )


@app.get("/ask", response_model=AskEnvelope)
def ask(
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_impl(q, x_orion_token)


@app.get("/v1/ask", response_model=AskEnvelope)
def ask_v1(
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_impl(q, x_orion_token)


def _ask_with_visuals_impl(
    q: str = Query(..., min_length=3, max_length=800),
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
    return _response_envelope(
        result, execution_mode=resp.execution_mode, fallback_reason=resp.fallback_reason
    )


@app.get("/ask_with_visuals", response_model=AskWithVisualsEnvelope)
def ask_with_visuals(
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    fmt: str = Query("png", pattern="^(png|svg)$"),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_with_visuals_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


@app.get("/v1/ask_with_visuals", response_model=AskWithVisualsEnvelope)
def ask_with_visuals_v1(
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    fmt: str = Query("png", pattern="^(png|svg)$"),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_with_visuals_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


def _ask_with_analytics_exports_impl(
    q: str = Query(..., min_length=3, max_length=800),
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
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    fmt: str = Query("csv", pattern="^(csv|parquet)$"),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_with_analytics_exports_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)


@app.get("/v1/ask_with_analytics_exports", response_model=AskWithAnalyticsExportsEnvelope)
def ask_with_analytics_exports_v1(
    request: Request,
    q: str = Query(..., min_length=3, max_length=800),
    fmt: str = Query("csv", pattern="^(csv|parquet)$"),
    x_orion_token: str | None = Header(default=None),
):
    _check_rate_limit(_client_ip(request))
    return _ask_with_analytics_exports_impl(q=q, fmt=fmt, x_orion_token=x_orion_token)
