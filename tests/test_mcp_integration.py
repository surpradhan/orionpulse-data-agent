from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcp_server.server import (
    apply_standard_views,
    describe_table,
    export_specs,
    generate_dashboard_spec,
    generate_storyboard_spec,
    get_kpi_summary,
    list_tables,
    run_anomaly_detection,
    run_forecast,
    run_sql,
)


def test_mcp_list_tables_includes_core_objects() -> None:
    tables = set(list_tables())
    assert {"fact_sales", "dim_product", "dim_region"}.issubset(tables)


def test_mcp_describe_table_valid_table_returns_columns() -> None:
    cols = describe_table("fact_sales")
    assert isinstance(cols, list)
    assert cols
    assert all(isinstance(c, dict) for c in cols)
    assert any(c.get("name") == "net_revenue" for c in cols)


def test_mcp_describe_table_rejects_disallowed_table() -> None:
    with pytest.raises(ValueError):
        describe_table("sqlite_master")


def test_mcp_run_sql_allows_simple_select_with_limit() -> None:
    rows = run_sql("SELECT * FROM fact_sales", limit=3)
    assert isinstance(rows, list)
    assert len(rows) <= 3
    if rows:
        assert isinstance(rows[0], dict)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1; SELECT 2",
        "SELECT * FROM sqlite_master",
    ],
)
def test_mcp_run_sql_blocks_multi_statement_and_disallowed_objects(query: str) -> None:
    with pytest.raises(ValueError):
        run_sql(query)


def test_mcp_get_kpi_summary_contract() -> None:
    rows = get_kpi_summary(grain="month")
    assert isinstance(rows, list)
    if rows:
        assert isinstance(rows[0], dict)
        assert "net_revenue" in rows[0]


def test_mcp_forecast_contract_honors_horizon_bounds() -> None:
    out = run_forecast(metric="net_revenue", horizon=3)
    assert isinstance(out, dict)
    assert "forecast" in out
    assert "diagnostics" in out

    with pytest.raises(ValueError):
        run_forecast(metric="net_revenue", horizon=0)

    with pytest.raises(ValueError):
        run_forecast(metric="net_revenue", horizon=25)


def test_mcp_anomaly_detection_threshold_validation() -> None:
    rows = run_anomaly_detection(metric="net_revenue", threshold=2.0)
    assert isinstance(rows, list)

    with pytest.raises(ValueError):
        run_anomaly_detection(metric="net_revenue", threshold=0.5)

    with pytest.raises(ValueError):
        run_anomaly_detection(metric="net_revenue", threshold=5.5)


def test_mcp_generate_dashboard_and_storyboard_specs() -> None:
    dashboard = generate_dashboard_spec(template_name="exec_overview", filters_json='{"region":"APAC"}')
    storyboard = generate_storyboard_spec(goal="Quarterly business review", audience="exec", period="latest_quarter")

    assert isinstance(dashboard, dict)
    assert isinstance(storyboard, dict)
    assert "widgets" in dashboard
    assert "sections" in storyboard


def test_mcp_generate_dashboard_spec_rejects_bad_filters_json() -> None:
    with pytest.raises(json.JSONDecodeError):
        generate_dashboard_spec(template_name="exec_overview", filters_json="{bad json}")


def test_mcp_export_specs_writes_files(tmp_path: Path) -> None:
    out = export_specs(str(tmp_path))
    assert "Specs exported under" in out
    assert (tmp_path / "dashboard" / "exec_overview.json").exists()
    assert (tmp_path / "storyboard" / "qbr_storyboard.json").exists()


def test_mcp_apply_standard_views_executes_without_error() -> None:
    out = apply_standard_views()
    assert out == "Standard views from sql/views.sql applied successfully."
