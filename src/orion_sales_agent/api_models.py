"""API request/response models for OrionPulse web routes."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatPayload(BaseModel):
    """Request body for `/chat` endpoint."""

    q: str = Field(..., min_length=1, max_length=800)
    with_visuals: bool = False
    with_analytics: bool = False
    fmt: str = "png"


class ApiEnvelope(BaseModel):
    """Standard API envelope for JSON responses."""

    status: Literal["ok"]
    trace_id: str
    timestamp: str
    warnings: list[str]
    data: Any
    execution_mode: str | None = None
    fallback_reason: str | None = None


class KpiRow(BaseModel):
    period: str
    net_revenue: float
    margin: float
    units_sold: float
    asp: float
    margin_pct: float


class ForecastPointModel(BaseModel):
    period: str
    value: float
    lower: float | None = None
    upper: float | None = None


class ForecastDiagnostics(BaseModel):
    method: str | None = None
    train_points: int | None = None
    backtest_points: int | None = None
    mape: float | None = None
    smape: float | None = None
    rmse: float | None = None
    warnings: list[str] = Field(default_factory=list)
    residual_std: float | None = None
    interval_method: str | None = None
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class ForecastPayload(BaseModel):
    metric: str
    horizon: int
    history: list[ForecastPointModel]
    forecast: list[ForecastPointModel]
    assumptions: list[str]
    diagnostics: ForecastDiagnostics | None = None
    warning: str | None = None


class AgentResultPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    intent: str
    answer: str
    reasoning_summary: list[str]
    data: Any
    followups: list[str]


class VisualsResultPayload(AgentResultPayload):
    visuals: list[dict[str, Any]]
    artifacts_base: str


class AnalyticsExportsResultPayload(AgentResultPayload):
    analytics_exports: dict[str, Any]
    artifacts_base: str
    semantic_specs_base: str


class ChatEnvelope(ApiEnvelope):
    data: AgentResultPayload


class KpiEnvelope(ApiEnvelope):
    data: list[KpiRow]


class ForecastEnvelope(ApiEnvelope):
    data: ForecastPayload


class AskEnvelope(ApiEnvelope):
    data: AgentResultPayload


class AskWithVisualsEnvelope(ApiEnvelope):
    data: VisualsResultPayload


class AskWithAnalyticsExportsEnvelope(ApiEnvelope):
    data: AnalyticsExportsResultPayload
