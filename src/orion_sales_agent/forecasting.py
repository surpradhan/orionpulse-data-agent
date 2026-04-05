"""Forecasting primitives: Holt-Winters ETS with holdout backtest and model selection."""

from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from math import sqrt
from typing import Any, TypedDict

import pandas as pd
from statsmodels.tools.sm_exceptions import ConvergenceWarning
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from .db import query_df

# Maps the public metric name to the exact column name in fact_sales.
# Used instead of f-string interpolation so the allowed set and the SQL
# identifier are defined in one place and injection is structurally impossible.
_METRIC_COLUMN: dict[str, str] = {
    "net_revenue": "net_revenue",
    "margin": "margin",
    "units_sold": "units_sold",
}


def _fit_ets(model: ExponentialSmoothing) -> Any:
    """Fit an ExponentialSmoothing model, suppressing ConvergenceWarning.

    statsmodels raises ConvergenceWarning when the L-BFGS-B optimiser does
    not fully converge. The returned fit is still usable (parameters are at
    the optimiser's best-found point), but pollutes logs and test output.
    """
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", ConvergenceWarning)
        fit = model.fit(optimized=True)
    if any(issubclass(w.category, ConvergenceWarning) for w in caught):
        logging.getLogger(__name__).debug(
            "ETS optimiser did not fully converge; using best-found parameters."
        )
    return fit


class ForecastDiagnostics(TypedDict):
    method: str
    train_points: int
    backtest_points: int
    mape: float | None
    smape: float | None
    rmse: float | None
    warnings: list[str]
    candidates: list[dict[str, float | str | int | None]]


@dataclass
class ForecastPoint:
    period: str
    value: float
    lower: float | None = None
    upper: float | None = None


def _empty_series_response(metric: str, horizon: int, reason: str) -> dict:
    """Return a normalized empty forecast payload with warning reason."""
    return {
        "metric": metric,
        "horizon": horizon,
        "history": [],
        "forecast": [],
        "assumptions": [],
        "warning": reason,
    }


def compute_forecast_diagnostics(
    series: pd.Series,
    horizon: int,
    backtest_window: int = 3,
    method: str = "holt_winters_v1",
) -> ForecastDiagnostics:
    """Compute backtest diagnostics (MAPE/sMAPE/RMSE) for forecast quality."""
    diag_warnings: list[str] = []
    candidates: list[dict[str, float | str | int | None]] = []
    n = int(len(series))
    if n < 8:
        return {
            "method": method,
            "train_points": max(0, n),
            "backtest_points": 0,
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": ["Insufficient series length for diagnostics"],
            "candidates": candidates,
        }

    backtest_points = min(max(1, int(backtest_window)), max(1, n // 4))
    if n - backtest_points < 6:
        backtest_points = max(1, n - 6)

    if backtest_points <= 0:
        diag_warnings.append("Backtest window resolved to zero; metrics unavailable")
        return {
            "method": method,
            "train_points": n,
            "backtest_points": 0,
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": diag_warnings,
            "candidates": candidates,
        }

    train = series.iloc[:-backtest_points]
    test = series.iloc[-backtest_points:]
    if len(train) < 6:
        diag_warnings.append("Training segment too short for robust backtest")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": diag_warnings,
            "candidates": candidates,
        }

    methods: list[tuple[str, str | None]] = [("holt_linear_v1", None)]
    if len(train) >= 24:
        methods.append(("holt_winters_v1", "add"))

    pred: pd.Series | None = None
    selected_method = method
    for candidate_name, seasonal in methods:
        try:
            backtest_model = ExponentialSmoothing(
                train,
                trend="add",
                seasonal=seasonal,
                seasonal_periods=12 if seasonal else None,
            )
            backtest_fit = _fit_ets(backtest_model)
            candidate_pred = pd.Series(
                backtest_fit.forecast(len(test)).values, index=test.index
            ).astype(float)
            candidate_err = (test.astype(float) - candidate_pred).pow(2)
            candidate_rmse = (
                float(sqrt(float(candidate_err.mean()))) if len(candidate_err) else None
            )
            candidates.append(
                {
                    "method": candidate_name,
                    "train_points": int(len(train)),
                    "backtest_points": int(len(test)),
                    "rmse": candidate_rmse,
                }
            )
        except Exception as exc:
            candidates.append(
                {
                    "method": candidate_name,
                    "train_points": int(len(train)),
                    "backtest_points": int(len(test)),
                    "rmse": None,
                    "error": str(exc),
                }
            )

    successful = [c for c in candidates if isinstance(c.get("rmse"), int | float)]
    if not successful:
        diag_warnings.append("Backtest model failed for all candidate methods")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": diag_warnings,
            "candidates": candidates,
        }

    successful.sort(key=lambda c: float(c["rmse"]))  # type: ignore[arg-type]
    selected_method = str(successful[0]["method"])
    selected_seasonal = "add" if selected_method == "holt_winters_v1" else None
    try:
        final_model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal=selected_seasonal,
            seasonal_periods=12 if selected_seasonal else None,
        )
        final_fit = _fit_ets(final_model)
        pred = pd.Series(final_fit.forecast(len(test)).values, index=test.index).astype(float)
    except Exception as exc:
        diag_warnings.append(f"Backtest model failed: {exc}")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": diag_warnings,
            "candidates": candidates,
        }

    actual = test.astype(float)
    forecast = pred
    err = actual - forecast
    abs_err = err.abs()
    actual_abs = actual.abs()

    denom_mape = actual_abs.replace(0, pd.NA)
    ape = (abs_err / denom_mape).dropna()
    mape = float(ape.mean() * 100.0) if not ape.empty else None
    if mape is not None and mape < 0:
        mape = 0.0

    smape_denom = (actual_abs + forecast.abs()).replace(0, pd.NA)
    smape_vals = ((2.0 * abs_err) / smape_denom).dropna()
    smape = float(smape_vals.mean() * 100.0) if not smape_vals.empty else None
    if smape is not None and smape < 0:
        smape = 0.0

    rmse = float(sqrt((err.pow(2)).mean())) if len(err) else None

    return {
        "method": selected_method if method == "auto_select_v1" else method,
        "train_points": int(len(train)),
        "backtest_points": int(len(test)),
        "mape": mape,
        "smape": smape,
        "rmse": rmse,
        "warnings": diag_warnings,
        "candidates": candidates,
    }


def select_forecast_method(series: pd.Series) -> str:
    """Select forecast method using simple holdout RMSE comparison.

    Candidate set currently includes:
    - ``holt_linear_v1``
    - ``holt_winters_v1`` (only when enough history exists)
    """
    diagnostics = compute_forecast_diagnostics(series, horizon=3, method="auto_select_v1")
    candidates = diagnostics.get("candidates", [])
    ranked = [c for c in candidates if isinstance(c.get("rmse"), int | float)]
    if not ranked:
        return "holt_linear_v1"
    ranked.sort(key=lambda c: float(c["rmse"]))  # type: ignore[arg-type]
    return str(ranked[0]["method"])


def forecast_metric(db_path: str, metric: str = "net_revenue", horizon: int = 3) -> dict:
    """Generate near-term forecast with confidence bands and diagnostics.

    Uses Holt linear / Holt-Winters additive seasonality depending on series
    length. Returns graceful warning payloads for empty/insufficient history.
    """
    from dataclasses import asdict

    if metric not in _METRIC_COLUMN:
        raise ValueError("Unsupported metric")
    if not isinstance(horizon, int) or horizon < 1 or horizon > 24:
        raise ValueError("horizon must be an integer between 1 and 24")

    col = _METRIC_COLUMN[metric]
    df = query_df(
        db_path,
        f"""
        SELECT substr(order_date,1,7) AS period, SUM({col}) AS value
        FROM fact_sales
        GROUP BY 1
        ORDER BY 1
        """,
    )
    if df.empty:
        return _empty_series_response(metric, horizon, "No historical data available for forecast")

    if "period" not in df.columns or "value" not in df.columns:
        return _empty_series_response(metric, horizon, "Missing required series columns")

    df = df.dropna(subset=["period", "value"]).copy()
    if df.empty:
        return _empty_series_response(metric, horizon, "No non-null historical values available")

    if len(df) < 8:
        return _empty_series_response(
            metric, horizon, "Insufficient history: need at least 8 periods"
        )

    series = pd.Series(
        df["value"].values,
        index=pd.period_range(df.iloc[0]["period"], periods=len(df), freq="M"),
    )

    selected = select_forecast_method(series)
    seasonal = "add" if selected == "holt_winters_v1" else None
    method = selected
    try:
        model = ExponentialSmoothing(
            series,
            trend="add",
            seasonal=seasonal,
            seasonal_periods=12 if seasonal else None,
        )
        fit = _fit_ets(model)
        future = fit.forecast(horizon)
    except Exception as exc:
        return _empty_series_response(metric, horizon, f"Forecast model failed: {exc}")

    diagnostics = compute_forecast_diagnostics(series, horizon=horizon, method=method)

    resid_std = float(getattr(fit, "resid", pd.Series(dtype=float)).std() or 0.0)
    hist = [
        ForecastPoint(period=str(p), value=float(v)) for p, v in zip(series.index, series.values)
    ]
    pred: list[ForecastPoint] = []
    for i, (p, v) in enumerate(zip(future.index, future.values), start=1):
        spread = 1.96 * resid_std * sqrt(i) if resid_std > 0 else max(abs(float(v)) * 0.05, 1.0)
        pred.append(
            ForecastPoint(
                period=str(p),
                value=float(v),
                lower=float(v - spread),
                upper=float(v + spread),
            )
        )

    _method_label = (
        "Holt-Winters additive trend/seasonality"
        if selected == "holt_winters_v1"
        else "Holt linear (additive trend, no seasonality component)"
    )
    return {
        "metric": metric,
        "horizon": horizon,
        "history": [asdict(x) for x in hist[-12:]],
        "forecast": [asdict(x) for x in pred],
        "assumptions": [
            _method_label,
            "Historical seasonality is a useful proxy for near-term demand",
        ],
        "diagnostics": {
            "method": diagnostics["method"],
            "train_points": diagnostics["train_points"],
            "backtest_points": diagnostics["backtest_points"],
            "mape": diagnostics["mape"],
            "smape": diagnostics["smape"],
            "rmse": diagnostics["rmse"],
            "warnings": diagnostics["warnings"],
            "candidates": diagnostics["candidates"],
            "residual_std": resid_std,
            "interval_method": "approx_95pct_from_residual_std",
        },
    }
