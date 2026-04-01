"""Reliability and correctness regression tests for OrionPulse.

Covers:
- iloc[0] crash guard in _synthesize_forecast_answer (empty DataFrame)
- Forecast mape=None handled gracefully
- Race-condition fix: _save_plot and _register_chart use same lock
- Artifact TTL purge (_purge_old_charts)
- Data-driven dashboard and storyboard answers
- LLM circuit-breaker retry logic (_is_retryable)
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Agent synthesizers — crash guards
# ---------------------------------------------------------------------------

class TestSynthesizeForecastCrashGuard:
    """_synthesize_forecast_answer must never raise on edge-case inputs."""

    def _make_agent(self):
        from src.orion_sales_agent.agent import OrionAgent
        return OrionAgent()

    def test_empty_forecast_list_returns_string(self):
        agent = self._make_agent()
        result = agent._synthesize_forecast_answer("forecast revenue", {"forecast": [], "diagnostics": {}})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mape_none_in_diagnostics_no_crash(self):
        agent = self._make_agent()
        data = {
            "forecast": [{"period": "2024-01", "value": 100_000, "lower": 90_000, "upper": 110_000}],
            "diagnostics": {"mape": None, "method": "holt_winters", "candidates": []},
        }
        result = agent._synthesize_forecast_answer("forecast next month", data)
        assert isinstance(result, str)
        # mape=None should produce a graceful fallback note, not a crash
        assert "holt_winters" in result or "MAPE not available" in result

    def test_top_performing_region_with_empty_db_result(self):
        """If the DB returns empty for region lookup, answer must still be returned."""
        import pandas as pd
        agent = self._make_agent()
        with patch("src.orion_sales_agent.agent.query_df", return_value=pd.DataFrame()):
            result = agent._synthesize_forecast_answer(
                "forecast for the top performing region",
                {"forecast": [], "diagnostics": {}},
            )
        assert isinstance(result, str)

    def test_zero_first_value_no_zerodivision(self):
        """Trend calculation must not divide by zero."""
        agent = self._make_agent()
        data = {
            "forecast": [
                {"period": "2024-01", "value": 0, "lower": 0, "upper": 0},
                {"period": "2024-02", "value": 0, "lower": 0, "upper": 0},
            ],
            "diagnostics": {},
        }
        result = agent._synthesize_forecast_answer("forecast", data)
        assert isinstance(result, str)


class TestSynthesizeAnomalyEdgeCases:
    def _make_agent(self):
        from src.orion_sales_agent.agent import OrionAgent
        return OrionAgent()

    def test_empty_list_returns_clean_message(self):
        agent = self._make_agent()
        result = agent._synthesize_anomaly_answer("any anomalies?", [])
        assert "no anomalies" in result.lower()

    def test_single_anomaly_does_not_crash(self):
        agent = self._make_agent()
        result = agent._synthesize_anomaly_answer(
            "anomaly?",
            [{"period": "2024-03", "value": 500_000, "zscore": 3.1}],
        )
        assert "2024-03" in result


class TestSynthesizeDashboard:
    def _make_agent(self):
        from src.orion_sales_agent.agent import OrionAgent
        return OrionAgent()

    def test_empty_widgets_fallback(self):
        agent = self._make_agent()
        result = agent._synthesize_dashboard_answer("dashboard", {"widgets": []})
        assert isinstance(result, str) and len(result) > 0

    def test_widget_count_in_answer(self):
        agent = self._make_agent()
        data = {"widgets": [{"type": "kpi", "title": "Revenue"}, {"type": "chart", "title": "Trend"}]}
        result = agent._synthesize_dashboard_answer("dashboard", data)
        assert "2" in result

    def test_no_crash_on_missing_keys(self):
        agent = self._make_agent()
        result = agent._synthesize_dashboard_answer("dashboard", {})
        assert isinstance(result, str)


class TestSynthesizeStoryboard:
    def _make_agent(self):
        from src.orion_sales_agent.agent import OrionAgent
        return OrionAgent()

    def test_empty_slides_fallback(self):
        agent = self._make_agent()
        result = agent._synthesize_storyboard_answer("storyboard", {"slides": [], "goal": "Q3 review"})
        assert isinstance(result, str)

    def test_slide_titles_in_answer(self):
        agent = self._make_agent()
        data = {
            "goal": "Q3 review",
            "slides": [{"title": "Context"}, {"title": "Insights"}, {"title": "Actions"}],
        }
        result = agent._synthesize_storyboard_answer("storyboard", data)
        assert "Context" in result
        assert "3" in result


# ---------------------------------------------------------------------------
# Visualization — lock coverage and TTL purge
# ---------------------------------------------------------------------------

class TestVisualizationLock:
    def test_chart_lock_and_manifest_lock_are_same_object(self):
        """_CHART_LOCK and _MANIFEST_LOCK must be the same lock (backwards compat alias)."""
        from src.orion_sales_agent.visualization import _CHART_LOCK, _MANIFEST_LOCK
        assert _CHART_LOCK is _MANIFEST_LOCK

    def test_save_plot_acquires_lock(self, tmp_path, monkeypatch):
        """_save_plot must acquire _CHART_LOCK before writing."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from src.orion_sales_agent import visualization as viz

        monkeypatch.setattr(viz, "CHART_DIR", tmp_path)
        monkeypatch.setattr(viz, "MANIFEST", tmp_path / "manifest.json")

        lock_acquired = []
        original_lock = viz._CHART_LOCK

        class SpyLock:
            def __enter__(self):
                lock_acquired.append(True)
                return original_lock.__enter__()
            def __exit__(self, *args):
                return original_lock.__exit__(*args)

        monkeypatch.setattr(viz, "_CHART_LOCK", SpyLock())

        fig, ax = plt.subplots()
        ax.plot([1, 2], [3, 4])
        viz._save_plot(fig, "test_chart", "png")

        assert lock_acquired, "_save_plot did not acquire _CHART_LOCK"


class TestArtifactTTLPurge:
    def test_purge_removes_old_files(self, tmp_path, monkeypatch):
        from src.orion_sales_agent import visualization as viz
        monkeypatch.setattr(viz, "CHART_DIR", tmp_path)

        # Create a file and backdate its mtime to 2 days ago
        old_file = tmp_path / "old_chart_20240101.png"
        old_file.write_bytes(b"fake png")
        two_days_ago = time.time() - 2 * 86_400
        import os
        os.utime(old_file, (two_days_ago, two_days_ago))

        # Fresh file — should be kept
        new_file = tmp_path / "new_chart_20240102.png"
        new_file.write_bytes(b"fake png")

        removed = viz._purge_old_charts(ttl_seconds=86_400)
        assert removed == 1
        assert not old_file.exists()
        assert new_file.exists()

    def test_purge_zero_when_no_old_files(self, tmp_path, monkeypatch):
        from src.orion_sales_agent import visualization as viz
        monkeypatch.setattr(viz, "CHART_DIR", tmp_path)
        removed = viz._purge_old_charts(ttl_seconds=86_400)
        assert removed == 0

    def test_purge_is_exposed_as_public_api(self):
        from src.orion_sales_agent.visualization import purge_old_charts
        assert callable(purge_old_charts)


# ---------------------------------------------------------------------------
# LLM client — circuit breaker retry
# ---------------------------------------------------------------------------

class TestLlmCircuitBreaker:
    def test_is_retryable_429(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        exc = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_resp)
        assert _is_retryable(exc) is True

    def test_is_retryable_503(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        exc = httpx.HTTPStatusError("service unavailable", request=MagicMock(), response=mock_resp)
        assert _is_retryable(exc) is True

    def test_is_not_retryable_400(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        exc = httpx.HTTPStatusError("bad request", request=MagicMock(), response=mock_resp)
        assert _is_retryable(exc) is False

    def test_is_not_retryable_401(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        exc = httpx.HTTPStatusError("unauthorized", request=MagicMock(), response=mock_resp)
        assert _is_retryable(exc) is False

    def test_is_retryable_connect_error(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        assert _is_retryable(httpx.ConnectError("connection refused")) is True

    def test_is_retryable_timeout(self):
        import httpx
        from src.orion_sales_agent.llm_client import _is_retryable
        assert _is_retryable(httpx.ReadTimeout("timed out")) is True

    def test_llm_chat_raises_when_not_configured(self):
        from src.orion_sales_agent.llm_client import llm_chat
        with patch("src.orion_sales_agent.llm_client.llm_enabled", return_value=False):
            with pytest.raises(RuntimeError, match="LLM not configured"):
                llm_chat("system", "user")
