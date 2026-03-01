from __future__ import annotations

from dataclasses import asdict, dataclass
from math import sqrt

import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from .db import query_df


def _empty_series_response(metric: str, horizon: int, reason: str) -> dict:
    return {
        "metric": metric,
        "horizon": horizon,
        "history": [],
        "forecast": [],
        "assumptions": [],
        "warning": reason,
    }


def kpi_summary(db_path: str, grain: str = "month", period_filter: str | None = None) -> list[dict]:
    if grain not in {"month", "quarter"}:
        raise ValueError("grain must be month or quarter")

    period_expr = "substr(order_date, 1, 7)" if grain == "month" else "substr(order_date, 1, 4) || '-Q' || ((cast(substr(order_date,6,2) as int)+2)/3)"
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
        return _empty_series_response(metric, horizon, "Insufficient history: need at least 8 periods")

    series = pd.Series(df["value"].values, index=pd.period_range(df.iloc[0]["period"], periods=len(df), freq="M"))

    seasonal = "add" if len(series) >= 24 else None
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

    resid_std = float(getattr(fit, "resid", pd.Series(dtype=float)).std() or 0.0)
    hist = [ForecastPoint(period=str(p), value=float(v)) for p, v in zip(series.index, series.values)]
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
            "residual_std": resid_std,
            "interval_method": "approx_95pct_from_residual_std",
        },
    }


def anomaly_detection(db_path: str, metric: str = "net_revenue", threshold: float = 2.0) -> list[dict]:
    if metric not in {"net_revenue", "margin", "units_sold"}:
        raise ValueError("Unsupported metric")
    if not isinstance(threshold, (int, float)) or threshold < 1.0 or threshold > 5.0:
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
