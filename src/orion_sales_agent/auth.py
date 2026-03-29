"""Authentication and authorization helpers for web/API channels."""
from __future__ import annotations

import hmac

from fastapi import HTTPException

from .config import auth_tokens_configured, settings


def auth_is_configured() -> bool:
    """Return whether analyst/admin tokens are configured."""

    return auth_tokens_configured(settings)


def require_role(x_orion_token: str | None, required_role: str) -> None:
    """Enforce endpoint role authorization.

    Args:
        x_orion_token: Token supplied by client request header.
        required_role: Either ``analyst`` or ``admin``.

    Raises:
        HTTPException: For unauthorized/forbidden requests or invalid role config.
    """

    token = (x_orion_token or "").strip()
    # If auth is not required and tokens are not configured, keep local/dev mode open.
    if not settings.auth_required and not auth_is_configured():
        return

    if required_role == "analyst":
        if settings.analyst_token and hmac.compare_digest(token, settings.analyst_token):
            return
        if settings.admin_token and hmac.compare_digest(token, settings.admin_token):
            return
        raise HTTPException(status_code=401, detail="Unauthorized: analyst token required")
    if required_role == "admin":
        if settings.admin_token and hmac.compare_digest(token, settings.admin_token):
            return
        raise HTTPException(status_code=403, detail="Forbidden: admin token required")
    raise HTTPException(status_code=500, detail="Invalid role requirement")
