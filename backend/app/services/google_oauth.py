"""
Google OAuth service.

Verifies Google ID tokens via Google's JWKS endpoint, using PyJWT +
cryptography (both already in requirements.txt — we deliberately avoid
``python-jose`` which is not).  When an ``id_token`` is not available we
fall back to exchanging an ``access_token`` for user info via Google's
userinfo endpoint.

Set these environment variables to enable:

- GOOGLE_CLIENT_ID     — required in production
- GOOGLE_CLIENT_SECRET — optional, only for OAuth-code flows
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import httpx
import jwt as pyjwt  # PyJWT (already a dep)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_TOKEN_INFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


_jwks_cache: dict[str, Any] = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


async def _fetch_jwks() -> dict[str, Any]:
    """Fetch and cache Google's JWKS for ID-token verification."""
    now = time.time()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL_SECONDS:
        return _jwks_cache["keys"]
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GOOGLE_JWKS_URL)
        resp.raise_for_status()
        keys = resp.json()
        _jwks_cache["keys"] = keys
        _jwks_cache["fetched_at"] = now
        return keys


def _find_key_for_kid(jwks: dict[str, Any], kid: str | None) -> dict[str, Any] | None:
    if not kid:
        return None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def _jwk_to_pem(jwk: dict[str, Any]) -> bytes:
    """Convert a JSON Web Key (RSA) to PEM-encoded DER bytes via cryptography."""
    n_b64 = jwk["n"]
    e_b64 = jwk["e"]

    # Re-add missing padding for urlsafe-base64
    def _b64url_to_int(value: str) -> int:
        pad = "=" * (-len(value) % 4)
        return int.from_bytes(base64.urlsafe_b64decode(value + pad), "big")

    n = _b64url_to_int(n_b64)
    e = _b64url_to_int(e_b64)

    public_numbers = __import__("cryptography.hazmat.primitives.asymmetric.rsa", fromlist=["RSAPublicNumbers"]).RSAPublicNumbers(e, n)
    public_key: RSAPublicKey = public_numbers.public_key()  # type: ignore[assignment]
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


async def _verify_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Google ID token using JWKS and return the claims."""
    try:
        header = pyjwt.get_unverified_header(id_token)
    except pyjwt.PyJWTError as exc:
        raise ValueError(f"Malformed Google ID token: {exc}") from exc

    jwks = await _fetch_jwks()
    key = _find_key_for_kid(jwks, header.get("kid"))
    if not key:
        # Refresh JWKS once in case keys rotated
        _jwks_cache["keys"] = None
        jwks = await _fetch_jwks()
        key = _find_key_for_kid(jwks, header.get("kid"))
    if not key:
        raise ValueError("Google signing key not found in JWKS")

    try:
        pem = _jwk_to_pem(key)
        public_key = serialization.load_pem_public_key(pem)
        claims = pyjwt.decode(
            id_token,
            public_key,
            algorithms=[header.get("alg", "RS256")],
            audience=settings.google_client_id or None,
            options={"verify_aud": bool(settings.google_client_id)},
        )
    except pyjwt.PyJWTError as exc:
        raise ValueError(f"Google ID token verification failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Google ID token verification failed: {exc}") from exc

    if claims.get("exp", 0) < int(time.time()):
        raise ValueError("Google ID token expired")
    return claims


async def _verify_access_token(access_token: str) -> dict[str, Any]:
    """Verify a Google access token by calling userinfo."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if resp.status_code != 200:
            # Fallback: try the tokeninfo endpoint
            resp2 = await client.get(
                GOOGLE_TOKEN_INFO_URL, params={"access_token": access_token}
            )
            if resp2.status_code != 200:
                raise ValueError("Google access token is invalid")
            try:
                data = resp2.json()
            except json.JSONDecodeError as exc:
                raise ValueError("Google tokeninfo returned non-JSON") from exc
            if (
                data.get("aud")
                and settings.google_client_id
                and data["aud"] != settings.google_client_id
            ):
                raise ValueError(
                    "Google access token was issued for a different client"
                )
            return {
                "email": data.get("email"),
                "email_verified": data.get("email_verified", "true").lower() == "true",
                "name": data.get("name") or "",
                "picture": data.get("picture"),
            }
        try:
            return resp.json()
        except json.JSONDecodeError as exc:
            raise ValueError("Google userinfo returned non-JSON") from exc


async def verify_google_token(
    id_token: str | None, access_token: str | None
) -> dict[str, Any]:
    """
    Verify a Google token and return a normalized profile.

    Returns a dict with at least ``email``.  Raises ``ValueError`` on failure.
    """
    if id_token:
        return await _verify_id_token(id_token)
    if access_token:
        return await _verify_access_token(access_token)
    raise ValueError("Either id_token or access_token is required")
