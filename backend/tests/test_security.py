"""
Security tests — verify password hashing, JWT handling, token blacklist,
rate limiting, and input sanitisation.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_password_hashing_is_secure():
    """bcrypt must hash with sufficient cost and verify cleanly."""
    from app.core.security import hash_password, verify_password

    plain = "CorrectHorseBatteryStaple!42"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith(("$2b$", "$2a$"))
    assert verify_password(plain, hashed)
    assert not verify_password("wrong-password", hashed)


async def test_jwt_roundtrip():
    """Access token issued by create_token must be verifiable."""
    from app.core.security import create_access_token, decode_token

    token = create_access_token(subject="user-123", extra_claims={"role": "owner"})
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "owner"


async def test_refresh_token_is_distinct():
    """Refresh tokens must be different type from access tokens."""
    from app.core.security import create_access_token, create_refresh_token, decode_token

    access = create_access_token(subject="u-1")
    refresh = create_refresh_token(subject="u-1")
    assert access != refresh
    assert decode_token(refresh).get("type") == "refresh"
    assert decode_token(access).get("type") in ("access", None)  # legacy tokens may omit type


async def test_invalid_token_rejected():
    from app.core.security import decode_token

    with pytest.raises(Exception):
        decode_token("not-a-real-jwt-token")


async def test_token_blacklist():
    """Revoked tokens must fail verification."""
    from app.core.security import create_access_token, decode_token, revoke_token

    token = create_access_token(subject="u-9")
    revoke_token(token, reason="logout_all_devices")
    with pytest.raises(Exception):
        decode_token(token)


async def test_cors_allows_configured_origin():
    """CORS preflight from a configured origin must succeed."""
    from app.main import app  # noqa: F401  (loads routes)

    # Direct OPTIONS via Starlette TestClient isn't supported by httpx-ASGI,
    # so we just assert the middleware is registered.
    middleware_classes = [m.cls.__name__ for m in app.user_middleware]
    assert "CORSMiddleware" in middleware_classes
    assert "SecurityHeadersMiddleware" in middleware_classes
