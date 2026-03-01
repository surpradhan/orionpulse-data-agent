from __future__ import annotations

from datetime import datetime, timezone


def dashboard_spec(template_name: str = "exec_overview", filters: dict | None = None) -> dict:
    filters = filters or {"date_grain": "month", "region": "ALL", "category": "ALL"}
    return {
        "name": template_name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filters": filters,
        "widgets": [
            {"id": "kpi_revenue", "type": "kpi", "metric": "net_revenue", "title": "Net Revenue"},
            {"id": "kpi_margin_pct", "type": "kpi", "metric": "margin_pct", "title": "Margin %"},
            {
                "id": "trend_revenue",
                "type": "line",
                "x": "period",
                "y": "net_revenue",
                "dataset": "vw_monthly_sales",
                "title": "Revenue Trend",
            },
            {
                "id": "region_perf",
                "type": "bar",
                "x": "region_name",
                "y": "net_revenue",
                "dataset": "vw_region_performance",
                "title": "Region Performance",
            },
        ],
    }


def storyboard_spec(goal: str, audience: str = "exec", period: str = "latest_quarter") -> dict:
    return {
        "goal": goal,
        "audience": audience,
        "period": period,
        "sections": [
            {"name": "Context", "prompt": "Summarize top-line revenue and margin trend."},
            {"name": "Insights", "prompt": "Highlight key drivers by region/product and anomalies."},
            {"name": "Prediction", "prompt": "Provide next-period forecast with assumptions."},
            {"name": "Actions", "prompt": "Recommend top 3 actions with expected business impact."},
        ],
    }
