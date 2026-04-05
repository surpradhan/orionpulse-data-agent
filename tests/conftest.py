from __future__ import annotations

import pytest

from src.orion_sales_agent.visualization import set_test_safe_matplotlib_backend

set_test_safe_matplotlib_backend()


@pytest.fixture(autouse=True)
def _reset_rate_bucket_testclient():
    """Clear the rate-limit bucket for the synthetic 'testclient' IP before each test.

    FastAPI's TestClient uses 'testclient' as the client host.  Without this
    fixture, timestamps left by earlier tests accumulate and cause spurious
    429s in load/burst tests.
    """
    from src.orion_sales_agent.webapp import _rate_limiter

    _rate_limiter.reset_key("testclient")
    yield
