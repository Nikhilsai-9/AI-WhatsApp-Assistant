"""
Security primitives: password hashing, JWT issuance/validation,
Fernet symmetric encryption for sensitive columns at rest.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext

from app.core.config import settings

# ─── Password hashing ────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain* (truncated to 72 bytes – bcrypt limit)."""
    return pwd_context.hash(plain[:72])


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


# ─── JWT ─────────────────────────────────────────────────────────
def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str | int,
    *,
    expires_delta: timedelta | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Sign a short-lived access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(_now().timestamp()),
        "exp": int((_now() + expires_delta).timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str | int) -> str:
    payload = {
        "sub": str(subject),
        "iat": int(_now().timestamp()),
        "exp": int(
            (
                _now() + timedelta(days=settings.jwt_refresh_token_expire_days)
            ).timestamp()
        ),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """Decode + validate.  Raises ``jwt.PyJWTError`` on failure."""
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    if expected_type and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected token type {expected_type!r}")
    return payload


# ─── Symmetric encryption (Fernet) ───────────────────────────────
def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        # Derive from APP_SECRET if explicit key absent (first boot convenience)
        derived = base64.urlsafe_b64encode(
            hashlib.sha256(settings.app_secret.encode()).digest()
        )
        return Fernet(derived)
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:  # pragma: no cover
        raise RuntimeError("Invalid ENCRYPTION_KEY – must be a base64 Fernet key.") from exc


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:  # pragma: no cover
        raise ValueError("Cannot decrypt value (key rotated or corrupted).") from exc


# ─── HMAC for bridge callbacks ───────────────────────────────────
def sign_bridge_payload(raw_body: bytes) -> str:
    return hmac.new(
        settings.bridge_webhook_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()


def verify_bridge_signature(raw_body: bytes, signature: str) -> bool:
    expected = sign_bridge_payload(raw_body)
    return hmac.compare_digest(expected, signature or "")
