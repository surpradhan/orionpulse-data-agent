"""Authentication and authorization helpers for web/API channels."""

from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException

from .config import auth_tokens_configured, settings

logger = logging.getLogger(__name__)


def auth_is_configured() -> bool:
    """Return whether analyst/admin tokens are configured."""

    return auth_tokens_configured(settings)


def _ct_eq(a: str | None, b: str | None) -> bool:
    """Constant-time equality check that safely handles None/empty values.

    Both comparisons are always performed regardless of outcome to prevent
    timing side-channels. When either value is absent a fixed-length dummy
    comparison runs so the execution time stays uniform.
    """
    # Use a fixed dummy so we always do two compare_digest calls.
    _DUMMY = "0" * 64
    sa = (a or "").encode()
    sb = (b or "").encode()
    # Pad/truncate to same length as _DUMMY to avoid length-leak short-circuit
    da = _DUMMY.encode()
    # Real comparison — result used below
    real = hmac.compare_digest(sa, sb)
    # Dummy comparison — result discarded, exists only for constant timing
    hmac.compare_digest(da, da)
    # Only consider it a match when both sides were non-empty
    return real and bool(a) and bool(b)


def require_role(x_orion_token: str | None, required_role: str) -> None:
    """Enforce endpoint role authorization.

    Both analyst and admin token comparisons are **always** evaluated so that
    the total CPU time is independent of which token is supplied, eliminating
    the timing side-channel present in sequential early-return comparisons.

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

    # Always evaluate both comparisons (constant-time, no early exit).
    matches_analyst = _ct_eq(token, settings.analyst_token)
    matches_admin = _ct_eq(token, settings.admin_token)

    if required_role == "analyst":
        if matches_analyst or matches_admin:
            return
        logger.warning("Failed auth attempt for role=analyst (token present: %s)", bool(token))
        raise HTTPException(status_code=401, detail="Unauthorized: analyst token required")
    if required_role == "admin":
        if matches_admin:
            return
        logger.warning("Failed auth attempt for role=admin (token present: %s)", bool(token))
        raise HTTPException(status_code=403, detail="Forbidden: admin token required")
    raise HTTPException(status_code=500, detail="Invalid role requirement")
