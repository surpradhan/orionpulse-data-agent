"""Security regression tests for OrionPulse.

Covers:
- XSS / HTML injection via LLM output (_sanitize_text)
- Auth timing side-channel (_ct_eq / require_role)
- Constant-time comparison presence in auth module
"""
from __future__ import annotations

import inspect

import pytest

from src.orion_sales_agent.agent import _sanitize_text
from src.orion_sales_agent.auth import _ct_eq, require_role

# ---------------------------------------------------------------------------
# _sanitize_text
# ---------------------------------------------------------------------------

class TestSanitizeText:
    def test_strips_script_tag(self):
        # The sanitizer removes HTML tags — <script> and </script> wrappers are gone.
        # Inner text content is kept (it won't execute without the tag wrapper).
        result = _sanitize_text("<script>alert('xss')</script>Revenue grew 5%")
        assert "<script>" not in result
        assert "</script>" not in result
        assert "Revenue grew 5%" in result

    def test_strips_img_onerror(self):
        result = _sanitize_text('<img src=x onerror=alert(1)> margin improved')
        assert "<img" not in result
        assert "onerror" not in result
        assert "margin improved" in result

    def test_strips_inline_style_tag(self):
        result = _sanitize_text('<style>body{display:none}</style>Real answer here')
        assert "<style>" not in result
        assert "Real answer here" in result

    def test_preserves_plain_text(self):
        plain = "Revenue grew 12% in Q3. APAC led with $4.2M."
        assert _sanitize_text(plain) == plain

    def test_preserves_numbers_and_symbols(self):
        text = "Margin: 23.4% | Revenue: $1,200,000 | Units: 5,000"
        assert _sanitize_text(text) == text

    def test_handles_empty_string(self):
        assert _sanitize_text("") == ""

    def test_handles_none(self):
        result = _sanitize_text(None)
        assert result is None or result == ""

    def test_nested_tags_stripped(self):
        result = _sanitize_text("<b><i>bold italic</i></b> plain")
        assert "<b>" not in result
        assert "<i>" not in result
        assert "plain" in result


# ---------------------------------------------------------------------------
# _ct_eq
# ---------------------------------------------------------------------------

class TestCtEq:
    def test_matching_strings_return_true(self):
        assert _ct_eq("abc123", "abc123") is True

    def test_mismatched_strings_return_false(self):
        assert _ct_eq("abc123", "xyz789") is False

    def test_none_left_returns_false(self):
        assert _ct_eq(None, "abc123") is False

    def test_none_right_returns_false(self):
        assert _ct_eq("abc123", None) is False

    def test_both_none_returns_false(self):
        assert _ct_eq(None, None) is False

    def test_empty_string_returns_false(self):
        assert _ct_eq("", "") is False

    def test_prefix_match_not_sufficient(self):
        # Ensure substring match doesn't pass
        assert _ct_eq("secret", "secretXXX") is False


# ---------------------------------------------------------------------------
# require_role
# ---------------------------------------------------------------------------

class TestRequireRole:
    def test_none_token_never_matches(self):
        """A None token must never match any configured token value."""
        assert _ct_eq(None, "some-token") is False
        assert _ct_eq(None, "admin-secret") is False
        assert _ct_eq(None, "") is False

    def test_wrong_token_raises_for_admin(self, monkeypatch):
        """require_role raises when token doesn't match."""
        from src.orion_sales_agent.config import settings

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "analyst_token", "analyst-secret")
        monkeypatch.setattr(settings, "admin_token", "admin-secret")

        with pytest.raises(Exception):  # HTTPException 403
            require_role("wrong-token", "admin")

    def test_correct_admin_token_passes(self, monkeypatch):
        from src.orion_sales_agent.config import settings

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "analyst_token", "analyst-secret")
        monkeypatch.setattr(settings, "admin_token", "admin-secret")

        # Should not raise
        require_role("admin-secret", "admin")

    def test_analyst_token_passes_analyst_role(self, monkeypatch):
        from src.orion_sales_agent.config import settings

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "analyst_token", "analyst-secret")
        monkeypatch.setattr(settings, "admin_token", "admin-secret")

        require_role("analyst-secret", "analyst")

    def test_admin_token_also_passes_analyst_role(self, monkeypatch):
        """Admin token is a superset — should grant analyst access too."""
        from src.orion_sales_agent.config import settings

        monkeypatch.setattr(settings, "auth_required", True)
        monkeypatch.setattr(settings, "analyst_token", "analyst-secret")
        monkeypatch.setattr(settings, "admin_token", "admin-secret")

        require_role("admin-secret", "analyst")


# ---------------------------------------------------------------------------
# Structural: verify hmac.compare_digest is used in auth module
# ---------------------------------------------------------------------------

class TestAuthStructural:
    def test_compare_digest_present_in_auth_source(self):
        from src.orion_sales_agent import auth
        src = inspect.getsource(auth)
        assert "compare_digest" in src, (
            "auth.py must use hmac.compare_digest for constant-time comparison"
        )

    def test_ct_eq_helper_exists(self):
        from src.orion_sales_agent.auth import _ct_eq
        assert callable(_ct_eq)
