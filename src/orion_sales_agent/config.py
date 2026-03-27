from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # Optional dependency path; app can still run without dotenv auto-load.
    pass


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class AuthProfile(str, Enum):
    DEV_OPEN = "DEV_OPEN"
    DEV_GUARDED = "DEV_GUARDED"
    PROD_STRICT = "PROD_STRICT"


@dataclass
class Settings:
    env: str = os.getenv("ORION_ENV", "dev")
    db_path: str = os.getenv("ORION_DB_PATH", "data/orion_sales_agent.db")
    default_forecast_horizon: int = int(os.getenv("ORION_DEFAULT_FORECAST_HORIZON", "3"))
    default_grain: str = os.getenv("ORION_DEFAULT_GRAIN", "month")
    readonly_sql: bool = _env_bool("ORION_READONLY_SQL", True)
    admin_mode: bool = _env_bool("ORION_ADMIN_MODE", False)
    max_sql_limit: int = int(os.getenv("ORION_MAX_SQL_LIMIT", "500"))
    llm_api_key: str = os.getenv("ORION_LLM_API_KEY", "")
    llm_base_url: str = os.getenv("ORION_LLM_BASE_URL", "https://api.openai.com/v1")
    llm_model: str = os.getenv("ORION_LLM_MODEL", "gpt-4o-mini")
    llm_max_steps: int = int(os.getenv("ORION_LLM_MAX_STEPS", "4"))
    llm_json_retries: int = int(os.getenv("ORION_LLM_JSON_RETRIES", "2"))
    debug_trace: bool = _env_bool("ORION_AGENT_DEBUG_TRACE", False)
    trace_path: str = os.getenv("ORION_AGENT_TRACE_PATH", "artifacts/agent-traces")
    voice_provider: str = os.getenv("ORION_VOICE_PROVIDER", "browser")
    voice_lang: str = os.getenv("ORION_VOICE_LANG", "en-US")
    tts_voice: str = os.getenv("ORION_TTS_VOICE", "")
    analyst_token: str = os.getenv("ORION_ANALYST_TOKEN", "")
    admin_token: str = os.getenv("ORION_ADMIN_TOKEN", "")
    auth_required: bool = _env_bool("ORION_AUTH_REQUIRED", os.getenv("ORION_ENV", "dev") != "dev")
    auth_profile: str = os.getenv("ORION_AUTH_PROFILE", "")
    web_default_mode: str = os.getenv("ORION_WEB_DEFAULT_MODE", "auto")
    cli_default_mode: str = os.getenv("ORION_CLI_DEFAULT_MODE", "deterministic")


def auth_tokens_configured(cfg: Settings) -> bool:
    return bool(cfg.analyst_token.strip() or cfg.admin_token.strip())


def resolve_auth_profile(cfg: Settings) -> AuthProfile:
    raw = (cfg.auth_profile or "").strip().upper()
    if raw:
        try:
            return AuthProfile(raw)
        except ValueError as exc:
            raise ValueError(
                f"Invalid ORION_AUTH_PROFILE='{cfg.auth_profile}'. "
                f"Expected one of: {', '.join(p.value for p in AuthProfile)}"
            ) from exc

    env = (cfg.env or "dev").strip().lower()
    if env == "dev":
        return AuthProfile.DEV_GUARDED if cfg.auth_required else AuthProfile.DEV_OPEN
    return AuthProfile.PROD_STRICT


def validate_auth_configuration(cfg: Settings) -> None:
    profile = resolve_auth_profile(cfg)
    tokens_ready = auth_tokens_configured(cfg)
    env = (cfg.env or "dev").strip().lower()

    if profile == AuthProfile.PROD_STRICT and not cfg.auth_required:
        raise RuntimeError("PROD_STRICT requires ORION_AUTH_REQUIRED=true")

    if env != "dev" and not tokens_ready:
        raise RuntimeError(
            "Non-dev environment requires ORION_ANALYST_TOKEN and/or ORION_ADMIN_TOKEN"
            " to be configured"
        )

    if (
        profile in {AuthProfile.PROD_STRICT, AuthProfile.DEV_GUARDED}
        and cfg.auth_required
        and not tokens_ready
    ):
        raise RuntimeError(
            "Auth is required but no ORION_ANALYST_TOKEN/ORION_ADMIN_TOKEN is configured"
        )


settings = Settings()
