from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.orion_sales_agent.agent import OrionAgent
from src.orion_sales_agent.analytics import forecast_metric
from src.orion_sales_agent.config import settings
from src.orion_sales_agent.sql_policy import validate_readonly_select, validate_single_statement
from src.orion_sales_agent.visualization import generate_chart
from src.orion_sales_agent.webapp import app


def test_sql_policy_blocks_multi_statement():
    try:
        validate_single_statement("SELECT 1; SELECT 2")
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_sql_policy_allowlist():
    try:
        validate_readonly_select("SELECT * FROM sqlite_master", {"fact_sales"})
        assert False, "Expected ValueError"
    except ValueError:
        assert True


def test_forecast_has_intervals_and_diagnostics():
    out = forecast_metric(settings.db_path, metric="net_revenue", horizon=3)
    assert "diagnostics" in out
    assert isinstance(out["forecast"], list)
    if out["forecast"]:
        p = out["forecast"][0]
        assert "lower" in p and "upper" in p


def test_visualization_contract_chart_output():
    meta = generate_chart("kpi_trend", fmt="png")
    assert meta["chart_type"] == "kpi_trend"
    assert Path(meta["path"]).exists()


def test_llm_fallback_on_bad_json(monkeypatch):
    agent = OrionAgent()
    monkeypatch.setattr(settings, "llm_api_key", "dummy-key")

    def bad_llm(*args, **kwargs):
        return "not-json"

    monkeypatch.setattr(agent, "_llm_chat", bad_llm)
    resp = agent.answer("forecast next quarter")
    assert resp.intent in {"forecast", "kpi", "root_cause", "general", "storyboard", "dashboard", "anomaly"}


def test_web_auth_roles(monkeypatch):
    monkeypatch.setattr(settings, "analyst_token", "analyst123")
    monkeypatch.setattr(settings, "admin_token", "admin123")
    monkeypatch.setattr(settings, "auth_required", True)
    client = TestClient(app)

    r1 = client.get("/ask", params={"q": "show kpi summary"})
    assert r1.status_code == 401

    r2 = client.get("/ask", params={"q": "show kpi summary"}, headers={"x-orion-token": "analyst123"})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["status"] == "ok"
    assert "trace_id" in body2
    assert "timestamp" in body2
    assert "warnings" in body2
    assert "data" in body2

    r2b = client.get("/kpi", headers={"x-orion-token": "analyst123"})
    assert r2b.status_code == 200
    body2b = r2b.json()
    assert body2b["status"] == "ok"
    assert isinstance(body2b["data"], list)

    r2c = client.get("/forecast", headers={"x-orion-token": "analyst123"})
    assert r2c.status_code == 200
    body2c = r2c.json()
    assert body2c["status"] == "ok"
    assert isinstance(body2c["warnings"], list)
    assert isinstance(body2c["data"], dict)

    r3 = client.get("/ask_with_bi_exports", params={"q": "prepare bi exports"}, headers={"x-orion-token": "analyst123"})
    assert r3.status_code == 403

    r4 = client.get("/ask_with_bi_exports", params={"q": "prepare bi exports"}, headers={"x-orion-token": "admin123"})
    assert r4.status_code == 200
    body4 = r4.json()
    assert body4["status"] == "ok"
    assert "bi_exports" in body4["data"]


def test_auth_required_without_tokens_blocks_access(monkeypatch):
    monkeypatch.setattr(settings, "analyst_token", "")
    monkeypatch.setattr(settings, "admin_token", "")
    monkeypatch.setattr(settings, "auth_required", True)
    client = TestClient(app)

    r = client.get("/ask", params={"q": "show kpi summary"})
    assert r.status_code == 401
