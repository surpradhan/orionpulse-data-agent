from __future__ import annotations

from src.orion_sales_agent.config import AuthProfile
from src.orion_sales_agent.config import Settings
from src.orion_sales_agent.config import resolve_auth_profile
from src.orion_sales_agent.config import validate_auth_configuration


def _settings(**overrides) -> Settings:
    base = Settings()
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_resolve_auth_profile_defaults_for_dev_open() -> None:
    cfg = _settings(env="dev", auth_required=False, auth_profile="")
    assert resolve_auth_profile(cfg) == AuthProfile.DEV_OPEN


def test_resolve_auth_profile_defaults_for_dev_guarded() -> None:
    cfg = _settings(env="dev", auth_required=True, auth_profile="")
    assert resolve_auth_profile(cfg) == AuthProfile.DEV_GUARDED


def test_resolve_auth_profile_defaults_for_non_dev_strict() -> None:
    cfg = _settings(env="prod", auth_required=True, auth_profile="")
    assert resolve_auth_profile(cfg) == AuthProfile.PROD_STRICT


def test_explicit_invalid_profile_raises() -> None:
    cfg = _settings(env="dev", auth_required=False, auth_profile="bad_value")
    try:
        resolve_auth_profile(cfg)
        assert False, "expected ValueError for invalid profile"
    except ValueError:
        assert True


def test_prod_strict_requires_auth_required_true() -> None:
    cfg = _settings(env="prod", auth_required=False, auth_profile="PROD_STRICT")
    try:
        validate_auth_configuration(cfg)
        assert False, "expected RuntimeError for strict profile without auth_required"
    except RuntimeError:
        assert True


def test_non_dev_requires_token_configuration() -> None:
    cfg = _settings(
        env="staging",
        auth_required=True,
        auth_profile="PROD_STRICT",
        analyst_token="",
        admin_token="",
    )
    try:
        validate_auth_configuration(cfg)
        assert False, "expected RuntimeError when non-dev lacks tokens"
    except RuntimeError:
        assert True


def test_dev_open_with_no_tokens_is_allowed() -> None:
    cfg = _settings(env="dev", auth_required=False, auth_profile="DEV_OPEN", analyst_token="", admin_token="")
    validate_auth_configuration(cfg)
