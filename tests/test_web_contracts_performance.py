from __future__ import annotations

import time

from fastapi.testclient import TestClient

from src.orion_sales_agent import analytics_exports
from src.orion_sales_agent.config import settings
from src.orion_sales_agent import visualization
from src.orion_sales_agent.webapp import app


def _open_access(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "analyst_token", "")
    monkeypatch.setattr(settings, "admin_token", "")


def _stub_heavy_ops(monkeypatch) -> None:
    monkeypatch.setattr(
        visualization,
        "generate_insight_pack",
        lambda question, fmt="png": [{"chart_type": "stub", "path": f"artifacts/charts/stub.{fmt}", "question": question}],
    )
    monkeypatch.setattr(
        analytics_exports,
        "export_analytics_pack",
        lambda fmt="csv": {
            "generated_at": "stub",
            "format": fmt,
            "datasets": {"sales_monthly": f"artifacts/analytics_exports/sales_monthly.{fmt}"},
            "semantic_packs": {"kpi_dictionary.json": "specs/analytics_exports/kpi_dictionary.json"},
            "manifest": "artifacts/analytics_exports/manifest.json",
        },
    )


def test_web_contract_chat_and_ask_family(monkeypatch):
    _open_access(monkeypatch)
    _stub_heavy_ops(monkeypatch)
    client = TestClient(app)

    chat = client.post("/chat", json={"q": "show kpi summary", "with_visuals": False, "with_analytics": False, "fmt": "png"})
    assert chat.status_code == 200
    chat_body = chat.json()
    assert chat_body["status"] == "ok"
    assert isinstance(chat_body["trace_id"], str)
    assert isinstance(chat_body["warnings"], list)
    assert isinstance(chat_body["data"]["answer"], str)
    assert isinstance(chat_body["data"]["followups"], list)

    ask = client.get("/ask", params={"q": "why did margin change"})
    assert ask.status_code == 200
    ask_body = ask.json()
    assert ask_body["status"] == "ok"
    assert isinstance(ask_body["data"]["reasoning_summary"], list)

    visuals = client.get("/ask_with_visuals", params={"q": "show charts", "fmt": "png"})
    assert visuals.status_code == 200
    visuals_body = visuals.json()
    assert visuals_body["status"] == "ok"
    assert "visuals" in visuals_body["data"]
    assert visuals_body["data"]["artifacts_base"] == "/artifacts/charts"

    analytics = client.get("/ask_with_analytics_exports", params={"q": "prepare analytics exports", "fmt": "csv"})
    assert analytics.status_code == 200
    analytics_body = analytics.json()
    assert analytics_body["status"] == "ok"
    assert "analytics_exports" in analytics_body["data"]
    assert analytics_body["data"]["semantic_specs_base"] == "/specs/analytics_exports"


def test_home_route_serves_externalized_template(monkeypatch):
    _open_access(monkeypatch)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "OrionPulse Agent" in body
    assert "Ask Agent" in body


def test_web_contract_kpi_and_forecast(monkeypatch):
    _open_access(monkeypatch)
    _stub_heavy_ops(monkeypatch)
    client = TestClient(app)

    kpi = client.get("/kpi")
    assert kpi.status_code == 200
    kpi_body = kpi.json()
    assert kpi_body["status"] == "ok"
    assert isinstance(kpi_body["data"], list)
    if kpi_body["data"]:
        row = kpi_body["data"][0]
        for key in ["period", "net_revenue", "margin", "units_sold", "asp", "margin_pct"]:
            assert key in row

    forecast = client.get("/forecast")
    assert forecast.status_code == 200
    forecast_body = forecast.json()
    assert forecast_body["status"] == "ok"
    assert forecast_body["data"]["metric"] == "net_revenue"
    assert isinstance(forecast_body["data"]["history"], list)
    assert isinstance(forecast_body["data"]["forecast"], list)


def test_endpoint_smoke_latency_by_mode(monkeypatch):
    _open_access(monkeypatch)
    _stub_heavy_ops(monkeypatch)
    client = TestClient(app)

    timings: dict[str, dict[str, float]] = {}
    for mode in ("deterministic", "auto"):
        monkeypatch.setattr(settings, "web_default_mode", mode)
        mode_timings: dict[str, float] = {}

        start = time.perf_counter()
        chat = client.post("/chat", json={"q": "show kpi summary", "with_visuals": False, "with_analytics": False, "fmt": "png"})
        mode_timings["chat"] = time.perf_counter() - start
        assert chat.status_code == 200

        start = time.perf_counter()
        visuals = client.get("/ask_with_visuals", params={"q": "show charts", "fmt": "png"})
        mode_timings["ask_with_visuals"] = time.perf_counter() - start
        assert visuals.status_code == 200

        start = time.perf_counter()
        analytics = client.get("/ask_with_analytics_exports", params={"q": "prepare analytics exports", "fmt": "csv"})
        mode_timings["ask_with_analytics_exports"] = time.perf_counter() - start
        assert analytics.status_code == 200

        for endpoint, value in mode_timings.items():
            assert value < 30.0, f"{endpoint} too slow in mode={mode}: {value:.2f}s"

        timings[mode] = mode_timings

    # Keep a lightweight relational check instead of strict absolute thresholds.
    assert timings["auto"]["chat"] < 30.0
