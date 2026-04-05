from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from src.orion_sales_agent.config import settings
from src.orion_sales_agent.webapp import app


def _open_access(monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_required", False)
    monkeypatch.setattr(settings, "analyst_token", "")
    monkeypatch.setattr(settings, "admin_token", "")


def _clear_rate_bucket(ip: str = "testclient") -> None:
    """Remove any accumulated rate-limit timestamps for *ip* before a load test."""
    from src.orion_sales_agent.webapp import _rate_limiter

    _rate_limiter.reset_key(ip)


def test_forecast_burst_concurrency(monkeypatch) -> None:
    _open_access(monkeypatch)
    _clear_rate_bucket()
    client = TestClient(app)

    def one_call() -> float:
        start = time.perf_counter()
        resp = client.get("/forecast")
        elapsed = time.perf_counter() - start
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert "data" in body and "forecast" in body["data"]
        return elapsed

    with ThreadPoolExecutor(max_workers=8) as pool:
        latencies = list(pool.map(lambda _: one_call(), range(16)))

    assert max(latencies) < 10.0


def test_kpi_sustained_load(monkeypatch) -> None:
    _open_access(monkeypatch)
    _clear_rate_bucket()
    client = TestClient(app)

    start = time.perf_counter()
    for _ in range(25):
        resp = client.get("/kpi")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert isinstance(body["data"], list)
    total = time.perf_counter() - start

    assert total < 20.0
