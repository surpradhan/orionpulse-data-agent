"""MCP tool server exposing OrionPulse analytics and metadata operations."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from src.orion_sales_agent.analytics import anomaly_detection, kpi_summary  # noqa: E402
from src.orion_sales_agent.config import settings  # noqa: E402
from src.orion_sales_agent.db import get_connection, query_df  # noqa: E402
from src.orion_sales_agent.forecasting import forecast_metric  # noqa: E402
from src.orion_sales_agent.specs import dashboard_spec, storyboard_spec  # noqa: E402
from src.orion_sales_agent.sql_policy import (  # noqa: E402
    validate_readonly_select,
    validate_single_statement,
    validate_with_sqlite_parser,
)
from src.orion_sales_agent.views import apply_views  # noqa: E402

mcp = FastMCP("orion-sales-agent")

ALLOWED_TABLES = {
    "fact_sales",
    "dim_product",
    "dim_region",
    "vw_monthly_sales",
    "vw_region_performance",
    "vw_product_margin_rank",
}
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _readonly_guard(query: str) -> None:
    """Apply coarse readonly guard for mutation keywords at statement start."""
    if not settings.readonly_sql:
        return
    q = query.strip().lower()
    forbidden = ("insert", "update", "delete", "drop", "alter", "create", "truncate", "replace")
    if q.startswith(forbidden):
        raise ValueError("Readonly SQL mode is enabled. Mutating statements are blocked.")


@mcp.tool()
def list_tables() -> list[str]:
    """List all SQLite tables and views available in current database."""
    with get_connection(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


@mcp.tool()
def describe_table(table_name: str) -> list[dict]:
    """Return schema metadata for an allowlisted table/view."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"table_name must be one of: {sorted(ALLOWED_TABLES)}")
    with get_connection(settings.db_path) as conn:
        # SQLite PRAGMA does not support parameterized binding for identifiers.
        # The allowlist check above is the injection guard; table_name is safe here.
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [dict(r) for r in rows]


@mcp.tool()
def run_sql(query: str, limit: int = 200) -> list[dict]:
    """Execute safe readonly SQL against allowlisted objects.

    Enforces single-statement validation, readonly constraints, parser-backed
    compilation checks, and result row caps.
    """
    if not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    limit = min(limit, settings.max_sql_limit)

    cleaned = validate_single_statement(query)
    _readonly_guard(query)
    cleaned = validate_readonly_select(cleaned, ALLOWED_TABLES)
    with get_connection(settings.db_path) as conn:
        validate_with_sqlite_parser(conn, cleaned)
    sql = f"SELECT * FROM ({cleaned}) LIMIT {int(limit)}"
    df = query_df(settings.db_path, sql)
    return df.to_dict(orient="records")


@mcp.tool()
def get_kpi_summary(period_filter: str = "", grain: str = "month") -> list[dict]:
    """Expose KPI summary tool with bounded input validation."""
    if grain not in {"month", "quarter"}:
        raise ValueError("grain must be month or quarter")
    if len(period_filter or "") > 40:
        raise ValueError("period_filter max length is 40")
    return kpi_summary(settings.db_path, grain=grain, period_filter=period_filter or None)


@mcp.tool()
def create_sql_view(view_name: str, definition: str) -> str:
    """Create or replace SQL view under admin-mode controls."""
    if settings.readonly_sql and not settings.admin_mode:
        raise PermissionError(
            "create_sql_view is disabled in readonly mode unless ORION_ADMIN_MODE=true"
        )
    if not settings.admin_mode:
        raise PermissionError("create_sql_view requires ORION_ADMIN_MODE=true")
    if not IDENTIFIER_RE.match(view_name):
        raise ValueError("Invalid view_name identifier")
    cleaned = validate_single_statement(definition)
    cleaned = validate_readonly_select(cleaned, ALLOWED_TABLES)

    with get_connection(settings.db_path) as conn:
        validate_with_sqlite_parser(conn, cleaned)
        conn.execute(f'DROP VIEW IF EXISTS "{view_name}"')
        conn.execute(f'CREATE VIEW "{view_name}" AS {cleaned}')
        conn.commit()
    return f"View '{view_name}' created successfully."


@mcp.tool()
def generate_dashboard_spec(template_name: str = "exec_overview", filters_json: str = "{}") -> dict:
    """Generate dashboard specification from template + JSON filters."""
    if len(template_name) > 60:
        raise ValueError("template_name too long")
    filters = json.loads(filters_json)
    if not isinstance(filters, dict):
        raise ValueError("filters_json must decode to an object")
    return dashboard_spec(template_name=template_name, filters=filters)


@mcp.tool()
def generate_storyboard_spec(
    goal: str, audience: str = "exec", period: str = "latest_quarter"
) -> dict:
    """Generate storyboard narrative specification."""
    if not goal or len(goal) > 200:
        raise ValueError("goal must be non-empty and <= 200 chars")
    if len(audience) > 50 or len(period) > 50:
        raise ValueError("audience/period too long")
    return storyboard_spec(goal=goal, audience=audience, period=period)


@mcp.tool()
def run_forecast(metric: str = "net_revenue", horizon: int = 3) -> dict:
    """Run metric forecast with validated horizon constraints."""
    if not isinstance(horizon, int) or horizon < 1 or horizon > 24:
        raise ValueError("horizon must be integer between 1 and 24")
    return forecast_metric(settings.db_path, metric=metric, horizon=horizon)


@mcp.tool()
def run_anomaly_detection(metric: str = "net_revenue", threshold: float = 2.0) -> list[dict]:
    """Run anomaly detection with bounded z-score threshold."""
    if not isinstance(threshold, int | float) or threshold < 1.0 or threshold > 5.0:
        raise ValueError("threshold must be between 1.0 and 5.0")
    return anomaly_detection(settings.db_path, metric=metric, threshold=threshold)


@mcp.tool()
def apply_standard_views() -> str:
    """Apply canonical SQL views from repository definitions."""
    apply_views(settings.db_path)
    return "Standard views from sql/views.sql applied successfully."


@mcp.tool()
def export_specs(output_dir: str = "specs") -> str:
    """Export default dashboard and storyboard specs to output directory."""
    out = Path(output_dir)
    (out / "dashboard").mkdir(parents=True, exist_ok=True)
    (out / "storyboard").mkdir(parents=True, exist_ok=True)
    (out / "dashboard" / "exec_overview.json").write_text(
        json.dumps(dashboard_spec(), indent=2), encoding="utf-8"
    )
    (out / "storyboard" / "qbr_storyboard.json").write_text(
        json.dumps(storyboard_spec(goal="Quarterly business review"), indent=2), encoding="utf-8"
    )
    return f"Specs exported under: {out.resolve()}"


if __name__ == "__main__":
    mcp.run()
