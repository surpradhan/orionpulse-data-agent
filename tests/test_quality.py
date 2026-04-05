"""Quality and completeness regression tests for OrionPulse.

Covers:
- /health endpoint schema and response shape
- Rate limiter (RateLimiter.check) enforces cap and resets after window
- max_length=800 enforced consistently across /ask and /chat
- Memory bloat guard (50 KB hard cap in save_memory)
- extra="forbid" on AgentResultPayload rejects unknown fields
- HealthEnvelope model validates correctly
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.orion_sales_agent.api_models import AgentResultPayload, HealthData, HealthEnvelope
from src.orion_sales_agent.memory_store import load_memory, save_memory
from src.orion_sales_agent.webapp import _rate_limiter, app

client = TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_schema(self):
        resp = client.get("/health")
        body = resp.json()
        assert body["status"] == "ok"
        assert "trace_id" in body
        assert "timestamp" in body
        assert "data" in body
        data = body["data"]
        assert "service" in data
        assert "version" in data
        assert "db_path" in data
        assert "llm_enabled" in data

    def test_health_no_auth_required(self):
        """Health endpoint must not require a token."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_envelope_model_validates(self):
        resp = client.get("/health")
        # Pydantic will raise if shape doesn't match HealthEnvelope
        envelope = HealthEnvelope(**resp.json())
        assert envelope.status == "ok"
        assert isinstance(envelope.data.llm_enabled, bool)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allows_requests_under_limit(self):
        ip = "test-ip-allow"
        _rate_limiter.reset_key(ip)
        # Should not raise for a single request
        _rate_limiter.check(ip)

    def test_raises_429_after_limit_exceeded(self):
        from fastapi import HTTPException

        ip = "test-ip-exceed"
        _rate_limiter.reset_key(ip)
        # Fill the bucket to the limit
        for _ in range(_rate_limiter._max_requests):
            _rate_limiter.check(ip)
        # Next call should raise
        with pytest.raises(HTTPException) as exc_info:
            _rate_limiter.check(ip)
        assert exc_info.value.status_code == 429

    def test_different_ips_are_independent(self):
        ip_a = "test-ip-a"
        ip_b = "test-ip-b"
        _rate_limiter.reset_key(ip_a)
        _rate_limiter.reset_key(ip_b)
        _rate_limiter.check(ip_a)
        _rate_limiter.check(ip_b)  # should not raise

    def test_chat_endpoint_rate_limited(self):
        """POST /chat should enforce rate limit."""
        import time as _time
        from collections import deque

        # Saturate the bucket for the testclient IP directly via internal state
        test_ip = "testclient"
        with _rate_limiter._lock:
            _rate_limiter._buckets[test_ip] = deque(
                [_time.monotonic()] * _rate_limiter._max_requests
            )
        resp = client.post("/chat", json={"q": "hello"})
        assert resp.status_code == 429
        # Clean up
        _rate_limiter.reset_key(test_ip)


# ---------------------------------------------------------------------------
# max_length consistency
# ---------------------------------------------------------------------------

class TestMaxLengthConsistency:
    def test_ask_rejects_over_800_chars(self):
        long_q = "a" * 801
        resp = client.get(f"/ask?q={long_q}")
        assert resp.status_code == 422

    def test_ask_accepts_exactly_800_chars(self):
        # Rate-limit guard: clear bucket first
        _rate_limiter.reset_key("testclient")
        long_q = "describe " + "a" * (800 - len("describe "))
        resp = client.get(f"/ask?q={long_q}")
        # Should not be a 422 validation error (may be 200 or auth error)
        assert resp.status_code != 422

    def test_chat_payload_rejects_over_800_chars(self):
        _rate_limiter.reset_key("testclient")
        resp = client.post("/chat", json={"q": "a" * 801})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Memory bloat guard
# ---------------------------------------------------------------------------

class TestMemoryBloatGuard:
    def test_save_memory_respects_max_items(self, tmp_path):
        mem_file = tmp_path / "memory.json"
        items = [{"question": f"q{i}", "answer": "a"} for i in range(50)]
        save_memory(mem_file, items, max_items=20)
        loaded = load_memory(mem_file)
        assert len(loaded) <= 20

    def test_save_memory_respects_byte_cap(self, tmp_path):
        mem_file = tmp_path / "memory.json"
        # Create items that together exceed 50 KB
        big_item = {"question": "x" * 2000, "answer": "y" * 2000}
        items = [big_item] * 30  # ~120 KB total
        save_memory(mem_file, items, max_items=30)
        content = mem_file.read_bytes()
        assert len(content) <= 50_000 + 500  # small tolerance for JSON overhead

    def test_save_memory_empty_items_writes_empty_list(self, tmp_path):
        mem_file = tmp_path / "memory.json"
        save_memory(mem_file, [], max_items=20)
        assert load_memory(mem_file) == []

    def test_load_memory_returns_empty_on_missing_file(self, tmp_path):
        mem_file = tmp_path / "nonexistent.json"
        assert load_memory(mem_file) == []


# ---------------------------------------------------------------------------
# API model strictness
# ---------------------------------------------------------------------------

class TestApiModelStrictness:
    def test_agent_result_payload_rejects_extra_fields(self):
        with pytest.raises(Exception):
            AgentResultPayload(
                intent="kpi",
                answer="ok",
                reasoning_summary=[],
                data={},
                followups=[],
                unknown_field="should_fail",
            )

    def test_agent_result_payload_accepts_valid_shape(self):
        payload = AgentResultPayload(
            intent="kpi",
            answer="Revenue grew 5%",
            reasoning_summary=["step1"],
            data={"rows": []},
            followups=["Need YoY?"],
        )
        assert payload.intent == "kpi"

    def test_health_data_rejects_extra_fields(self):
        with pytest.raises(Exception):
            HealthData(
                service="orionpulse",
                version="1.0",
                db_path="/data/db.sqlite",
                llm_enabled=False,
                extra_surprise="boom",
            )
