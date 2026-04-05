"""Tool registry for LLM planner orchestration actions."""
from __future__ import annotations

from typing import Any

from .analytics import anomaly_detection, kpi_summary
from .forecasting import forecast_metric
from .analytics_exports import export_analytics_pack
from .config import settings
from .db import query_df
from .specs import dashboard_spec, storyboard_spec
from .visualization import generate_chart, generate_insight_pack


def build_tool_registry() -> dict[str, Any]:
    """Return callable registry used by planner actions."""

    return {
        "kpi_summary": lambda args: kpi_summary(
            settings.db_path,
            grain=str(args.get("grain", settings.default_grain)),
            period_filter=args.get("period_filter"),
        ),
        "forecast": lambda args: forecast_metric(
            settings.db_path,
            metric=str(args.get("metric", "net_revenue")),
            horizon=int(args.get("horizon", settings.default_forecast_horizon)),
        ),
        "anomaly": lambda args: anomaly_detection(
            settings.db_path,
            metric=str(args.get("metric", "net_revenue")),
            threshold=float(args.get("threshold", 2.0)),
        ),
        "dashboard": lambda args: dashboard_spec(
            template_name=str(args.get("template_name", "exec_overview")),
            filters=args.get("filters") if isinstance(args.get("filters"), dict) else None,
        ),
        "storyboard": lambda args: storyboard_spec(
            goal=str(args.get("goal", "Executive review")),
            audience=str(args.get("audience", "exec")),
            period=str(args.get("period", "latest_quarter")),
        ),
        "top_regions": lambda args: query_df(
            settings.db_path,
            "SELECT * FROM vw_region_performance ORDER BY net_revenue DESC LIMIT 5",
        ).to_dict(orient="records"),
        "top_products": lambda args: query_df(
            settings.db_path,
            "SELECT * FROM vw_product_margin_rank ORDER BY margin_pct DESC LIMIT 5",
        ).to_dict(orient="records"),
        "generate_chart": lambda args: generate_chart(
            chart_type=str(args.get("chart_type", "kpi_trend")),
            metric=str(args.get("metric", "net_revenue")),
            horizon=int(args.get("horizon", settings.default_forecast_horizon)),
            threshold=float(args.get("threshold", 2.0)),
            fmt=str(args.get("fmt", "png")),
        ),
        "generate_insight_pack": lambda args: generate_insight_pack(
            question=str(args.get("question", "")),
            fmt=str(args.get("fmt", "png")),
        ),
        "export_analytics_pack": lambda args: export_analytics_pack(
            fmt=str(args.get("fmt", "csv"))
        ),
    }
