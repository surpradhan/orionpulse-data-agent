from __future__ import annotations

import pandas as pd

from src.orion_sales_agent.analytics import compute_forecast_diagnostics
from src.orion_sales_agent.analytics import forecast_metric
from src.orion_sales_agent.analytics import select_forecast_method
from src.orion_sales_agent.config import settings


def test_forecast_diagnostics_present_and_bounded() -> None:
    out = forecast_metric(settings.db_path, metric="net_revenue", horizon=3)
    diagnostics = out.get("diagnostics", {})
    assert "method" in diagnostics
    assert diagnostics.get("train_points", 0) >= 0
    assert diagnostics.get("backtest_points", 0) >= 0
    if diagnostics.get("mape") is not None:
        assert diagnostics["mape"] >= 0
    if diagnostics.get("smape") is not None:
        assert diagnostics["smape"] >= 0
    if diagnostics.get("rmse") is not None:
        assert diagnostics["rmse"] >= 0


def test_short_series_returns_nullable_metrics_with_warning() -> None:
    idx = pd.period_range("2024-01", periods=6, freq="M")
    series = pd.Series([100, 105, 102, 110, 108, 111], index=idx)
    diagnostics = compute_forecast_diagnostics(series=series, horizon=3)
    assert diagnostics["mape"] is None
    assert diagnostics["smape"] is None
    assert diagnostics["rmse"] is None
    assert diagnostics["warnings"]


def test_forecast_diagnostics_exposes_candidate_methods() -> None:
    out = forecast_metric(settings.db_path, metric="net_revenue", horizon=3)
    diagnostics = out.get("diagnostics", {})
    candidates = diagnostics.get("candidates", [])
    assert isinstance(candidates, list)
    if candidates:
        assert "method" in candidates[0]
        assert "rmse" in candidates[0]


def test_select_forecast_method_returns_supported_method() -> None:
    idx = pd.period_range("2022-01", periods=24, freq="M")
    series = pd.Series([100 + i * 2 for i in range(24)], index=idx)
    method = select_forecast_method(series)
    assert method in {"holt_linear_v1", "holt_winters_v1"}
