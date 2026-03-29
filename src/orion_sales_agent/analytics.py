"""Analytics primitives for KPI summaries, forecasting, and anomaly detection."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt
from typing import TypedDict

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from .db import query_df


class ForecastDiagnostics(TypedDict):
    method: str
    train_points: int
    backtest_points: int
    mape: float | None
    smape: float | None
    rmse: float | None
    warnings: list[str]
    candidates: list[dict[str, float | str | int | None]]


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


def kpi_summary(db_path: str, grain: str = "month", period_filter: str | None = None) -> list[dict]:
    """Compute period-aggregated KPI summary.

    Args:
        db_path: SQLite database path.
        grain: ``month`` or ``quarter`` aggregation.
        period_filter: Optional plain-text filter matched against period label.
    """
    if grain not in {"month", "quarter"}:
        raise ValueError("grain must be month or quarter")

    period_expr = (
        "substr(order_date, 1, 7)"
        if grain == "month"
        else "substr(order_date, 1, 4) || '-Q' || ((cast(substr(order_date,6,2) as int)+2)/3)"
    )
    sql = f"""
        SELECT
            {period_expr} AS period,
            SUM(net_revenue) AS net_revenue,
            SUM(margin) AS margin,
            SUM(units_sold) AS units_sold,
            CASE WHEN SUM(units_sold)=0 THEN 0 ELSE SUM(net_revenue)/SUM(units_sold) END AS asp,
            CASE WHEN SUM(net_revenue)=0 THEN 0 ELSE SUM(margin)/SUM(net_revenue) END AS margin_pct
        FROM fact_sales
        GROUP BY 1
        ORDER BY 1
    """
    df = query_df(db_path, sql)
    if df.empty:
        return []
    if period_filter:
        if len(period_filter) > 40:
            raise ValueError("period_filter too long")
        df = df[df["period"].str.contains(period_filter, regex=False)]
    return df.to_dict(orient="records")


@dataclass
class ForecastPoint:
    period: str
    value: float
    lower: float | None = None
    upper: float | None = None


def forecast_metric(db_path: str, metric: str = "net_revenue", horizon: int = 3) -> dict:
    """Generate near-term forecast with confidence bands and diagnostics.

    Uses Holt linear / Holt-Winters additive seasonality depending on series
    length. Returns graceful warning payloads for empty/insufficient history.
    """
    if metric not in {"net_revenue", "margin", "units_sold"}:
        raise ValueError("Unsupported metric")
    if not isinstance(horizon, int) or horizon < 1 or horizon > 24:
        raise ValueError("horizon must be an integer between 1 and 24")

    df = query_df(
        db_path,
        f"""
        SELECT substr(order_date,1,7) AS period, SUM({metric}) AS value
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
        fit = model.fit(optimized=True)
        future = fit.forecast(horizon)
    except Exception as exc:
        return _empty_series_response(metric, horizon, f"Forecast model failed: {exc}")

    diagnostics = compute_forecast_diagnostics(series, horizon=horizon, method=method)

    resid_std = float(getattr(fit, "resid", pd.Series(dtype=float)).std() or 0.0)
    hist = [
        ForecastPoint(period=str(p), value=float(v))
        for p, v in zip(series.index, series.values)
    ]
    pred: list[ForecastPoint] = []
    for i, (p, v) in enumerate(zip(future.index, future.values), start=1):
        # Primary: 95% CI widened by sqrt(steps) when residuals are available.
        # Fallback: 5% of forecast value (floored at 1.0) when model residuals are
        # zero or unavailable — this is a heuristic interval, not a statistical one.
        spread = 1.96 * resid_std * sqrt(i) if resid_std > 0 else max(abs(float(v)) * 0.05, 1.0)
        pred.append(
            ForecastPoint(
                period=str(p),
                value=float(v),
                lower=float(v - spread),
                upper=float(v + spread),
            )
        )

    return {
        "metric": metric,
        "horizon": horizon,
        "history": [asdict(x) for x in hist[-12:]],
        "forecast": [asdict(x) for x in pred],
        "assumptions": [
            "Holt-Winters additive trend/seasonality",
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
    ranked.sort(key=lambda c: float(c["rmse"]))
    return str(ranked[0]["method"])


def compute_forecast_diagnostics(
    series: pd.Series,
    horizon: int,
    backtest_window: int = 3,
    method: str = "holt_winters_v1",
) -> ForecastDiagnostics:
    """Compute backtest diagnostics (MAPE/sMAPE/RMSE) for forecast quality."""
    warnings: list[str] = []
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
        warnings.append("Backtest window resolved to zero; metrics unavailable")
        return {
            "method": method,
            "train_points": n,
            "backtest_points": 0,
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": warnings,
            "candidates": candidates,
        }

    train = series.iloc[:-backtest_points]
    test = series.iloc[-backtest_points:]
    if len(train) < 6:
        warnings.append("Training segment too short for robust backtest")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": warnings,
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
            backtest_fit = backtest_model.fit(optimized=True)
            candidate_pred = (
                pd.Series(backtest_fit.forecast(len(test)).values, index=test.index)
                .astype(float)
            )
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
        warnings.append("Backtest model failed for all candidate methods")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": warnings,
            "candidates": candidates,
        }

    successful.sort(key=lambda c: float(c["rmse"]))
    selected_method = str(successful[0]["method"])
    selected_seasonal = "add" if selected_method == "holt_winters_v1" else None
    try:
        final_model = ExponentialSmoothing(
            train,
            trend="add",
            seasonal=selected_seasonal,
            seasonal_periods=12 if selected_seasonal else None,
        )
        final_fit = final_model.fit(optimized=True)
        pred = pd.Series(final_fit.forecast(len(test)).values, index=test.index).astype(float)
    except Exception as exc:
        warnings.append(f"Backtest model failed: {exc}")
        return {
            "method": method,
            "train_points": int(len(train)),
            "backtest_points": int(len(test)),
            "mape": None,
            "smape": None,
            "rmse": None,
            "warnings": warnings,
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
        "warnings": warnings,
        "candidates": candidates,
    }


def anomaly_detection(
    db_path: str, metric: str = "net_revenue", threshold: float = 2.0
) -> list[dict]:
    """Detect outliers via z-score thresholding over monthly aggregated metric."""
    if metric not in {"net_revenue", "margin", "units_sold"}:
        raise ValueError("Unsupported metric")
    if not isinstance(threshold, int | float) or threshold < 1.0 or threshold > 5.0:
        raise ValueError("threshold must be a number between 1.0 and 5.0")

    df = query_df(
        db_path,
        f"""
        SELECT substr(order_date,1,7) AS period, SUM({metric}) AS value
        FROM fact_sales
        GROUP BY 1
        ORDER BY 1
        """,
    )
    if df.empty or "value" not in df.columns:
        return []
    mean = df["value"].mean()
    std = df["value"].std() or 1.0
    df["zscore"] = (df["value"] - mean) / std
    out = df[df["zscore"].abs() >= threshold].copy()
    return out.to_dict(orient="records")
