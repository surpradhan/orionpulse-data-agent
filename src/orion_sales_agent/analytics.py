"""Analytics primitives for KPI summaries and anomaly detection.

Forecasting (Holt-Winters ETS, diagnostics, model selection) lives in
``forecasting.py`` — import from there for forecast operations.
"""

from __future__ import annotations

from typing import Any, cast

from .db import query_df

# Maps the public metric name to the exact column name in fact_sales.
# Used instead of f-string interpolation so the allowed set and the SQL
# identifier are defined in one place and injection is structurally impossible.
_METRIC_COLUMN: dict[str, str] = {
    "net_revenue": "net_revenue",
    "margin": "margin",
    "units_sold": "units_sold",
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
    return cast(list[dict[str, Any]], df.to_dict(orient="records"))


def anomaly_detection(
    db_path: str, metric: str = "net_revenue", threshold: float = 2.0
) -> list[dict]:
    """Detect outliers via z-score thresholding over monthly aggregated metric."""
    if metric not in _METRIC_COLUMN:
        raise ValueError("Unsupported metric")
    if not isinstance(threshold, int | float) or threshold < 1.0 or threshold > 5.0:
        raise ValueError("threshold must be a number between 1.0 and 5.0")

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
    if df.empty or "value" not in df.columns:
        return []
    mean = df["value"].mean()
    std = df["value"].std() or 1.0
    df["zscore"] = (df["value"] - mean) / std
    out = df[df["zscore"].abs() >= threshold].copy()
    return cast(list[dict[str, Any]], out.to_dict(orient="records"))
