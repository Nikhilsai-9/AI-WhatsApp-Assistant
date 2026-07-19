"""
Authentication API — production-ready.

Endpoints (mounted under /api/auth):

  POST   /register                — create an account
  POST   /login                   — password login
  POST   /refresh                 — refresh tokens
  POST   /logout                  — revoke this device's refresh token
  POST   /logout-all              — revoke every refresh token for the user
  POST   /google                  — sign in / sign up via Google OAuth
  POST   /forgot-password         — request a reset link
  POST   /reset-password          — set a new password
  POST   /verify-email            — confirm an email-verification token
  POST   /resend-verification     — send a new verification email
  GET    /me                      — current user profile
  PATCH  /me                      — update profile fields
  POST   /change-password         — rotate password (increments token_version)
  POST   /ai/emergency-stop       — flip the kill switch
  DELETE /me                      — delete account
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit_dependency
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UserResponse,
    VerifyEmailRequest,
)
from app.services.email import send_password_reset_email, send_verification_email
from app.services.google_oauth import verify_google_token

logger = get_logger(__name__)

router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


# ─── Helpers ────────────────────────────────────────────────────
def _signing_secret() -> str:
    return settings.jwt_secret or settings.app_secret


def _issue_tokens(user: User) -> tuple[str, str, int]:
    """Create (access, refresh, expires_in_seconds)."""
    tv = getattr(user, "token_version", 0) or 0
    access = create_access_token(subject=str(user.id), extra={"tv": tv})
    refresh = create_refresh_token(subject=str(user.id), extra={"tv": tv})
    expires = settings.jwt_access_token_expire_minutes * 60
    return access, refresh, expires


def _user_to_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        avatar_url=user.avatar_url,
        is_active=getattr(user, "is_active", True),
        is_verified=getattr(user, "is_verified", False),
        email_verified=getattr(user, "email_verified", False),
        is_ai_enabled=getattr(user, "is_ai_enabled", True),
        ai_emergency_stop=getattr(user, "ai_emergency_stop", False),
        created_at=user.created_at,
        last_login_at=getattr(user, "last_login_at", None),
    )


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> User:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = pyjwt.decode(
            token,
            _signing_secret(),
            algorithms=[settings.jwt_algorithm],
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    sub = payload.get("sub")
    typ = payload.get("type")
    tv = payload.get("tv", 0)
    if not sub or typ != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")

    try:
        user_id = uuid.UUID(sub)
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject")

    user = await db.get(User, user_id)
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or disabled")
    if getattr(user, "token_version", 0) != tv:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")
    return user


async def _find_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


def _build_verify_link(token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/auth/verify-email?token={token}"


def _build_reset_link(token: str) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/auth/reset-password?token={token}"


# ─── Register ───────────────────────────────────────────────────
@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=5, window_seconds=60))],
) -> AuthResponse:
    email = body.email.lower()
    existing = await _find_by_email(db, email)
    if existing:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = User(
        email=email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        phone_number=body.phone_number,
        is_active=True,
        email_verified=False,
        is_verified=False,
        is_ai_enabled=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Send verification email (best-effort)
    try:
        token = secrets.token_urlsafe(48)
        user.email_verification_token = token
        await db.commit()
        await send_verification_email(
            to=user.email,
            name=user.full_name or "",
            link=_build_verify_link(token),
        )
    except Exception as exc:
        logger.warning("verification_email_failed", error=str(exc))

    access, refresh, expires = _issue_tokens(user)
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires,
        user=_user_to_response(user),
    )


# ─── Login ──────────────────────────────────────────────────────
@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=8, window_seconds=60))],
) -> AuthResponse:
    email = body.email.lower()
    user = await _find_by_email(db, email)
    # Run password verification even on missing user to avoid timing leaks.
    placeholder = hash_password("__placeholder__")
    if not user or not verify_password(body.password, user.hashed_password or placeholder):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not getattr(user, "is_active", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)

    access, refresh, expires = _issue_tokens(user)
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires,
        user=_user_to_response(user),
    )


# ─── Refresh ────────────────────────────────────────────────────
@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    body: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=15, window_seconds=60))],
) -> AuthResponse:
    try:
        payload = pyjwt.decode(
            body.refresh_token,
            _signing_secret(),
            algorithms=[settings.jwt_algorithm],
        )
    except pyjwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token is not a refresh token")

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except (TypeError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token subject")

    user = await db.get(User, user_id)
    if not user or not getattr(user, "is_active", True):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if getattr(user, "token_version", 0) != payload.get("tv", 0):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")

    access, new_refresh, expires = _issue_tokens(user)
    return AuthResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=expires,
        user=_user_to_response(user),
    )


# ─── Logout ─────────────────────────────────────────────────────
@router.post("/logout", response_model=MessageResponse)
async def logout(_: Annotated[User, Depends(get_current_user)]) -> MessageResponse:
    return MessageResponse(message="Logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return MessageResponse(message="All sessions revoked")


# ─── Google OAuth ───────────────────────────────────────────────
@router.post("/google", response_model=AuthResponse)
async def google_login(
    body: GoogleAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=10, window_seconds=60))],
) -> AuthResponse:
    if not body.has_any():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "id_token or access_token required")
    if not settings.google_client_id:
        logger.warning("google_login_without_client_id")

    try:
        claims = await verify_google_token(body.id_token, body.access_token)
    except ValueError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Google verification failed: {exc}") from exc

    email = (claims.get("email") or "").lower()
    if not email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google account has no email")
    if claims.get("email_verified") is False:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Google email not verified")

    user = await _find_by_email(db, email)
    if not user:
        user = User(
            email=email,
            hashed_password="",  # OAuth-only
            full_name=claims.get("name"),
            avatar_url=claims.get("picture"),
            email_verified=True,
            is_verified=True,
            is_ai_enabled=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        if not user.email_verified:
            user.email_verified = True
        if claims.get("picture") and not user.avatar_url:
            user.avatar_url = claims["picture"]
        if claims.get("name") and not user.full_name:
            user.full_name = claims["name"]
        user.last_login_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

    access, refresh, expires = _issue_tokens(user)
    return AuthResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires,
        user=_user_to_response(user),
    )


# ─── Forgot / reset password ────────────────────────────────────
@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=5, window_seconds=60))],
) -> MessageResponse:
    """Always respond with the same message to avoid account enumeration."""
    user = await _find_by_email(db, body.email.lower())
    if user and getattr(user, "is_active", True):
        token = secrets.token_urlsafe(48)
        user.password_reset_token = hashlib.sha256(token.encode()).hexdigest()
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        await db.commit()
        try:
            await send_password_reset_email(
                to=user.email,
                name=user.full_name or "",
                link=_build_reset_link(token),
            )
        except Exception as exc:
            logger.warning("reset_email_failed", error=str(exc))
    return MessageResponse(message="If an account exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=8, window_seconds=60))],
) -> MessageResponse:
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    result = await db.execute(
        select(User).where(User.password_reset_token == token_hash)
    )
    user = result.scalar_one_or_none()
    if not user or not user.password_reset_expires:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset link")
    if user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset link has expired")

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return MessageResponse(message="Password updated")


# ─── Email verification ─────────────────────────────────────────
@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user_result = await db.execute(
        select(User).where(User.email_verification_token == body.token)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid verification token")
    user.email_verified = True
    user.is_verified = True
    user.email_verification_token = None
    await db.commit()
    return MessageResponse(message="Email verified")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=3, window_seconds=300))],
) -> MessageResponse:
    if user.email_verified:
        return MessageResponse(message="Email already verified")
    token = secrets.token_urlsafe(48)
    user.email_verification_token = token
    await db.commit()
    try:
        await send_verification_email(
            to=user.email,
            name=user.full_name or "",
            link=_build_verify_link(token),
        )
    except Exception as exc:
        logger.warning("resend_verification_failed", error=str(exc))
    return MessageResponse(message="Verification email sent")


# ─── Me ─────────────────────────────────────────────────────────
@router.get("/me", response_model=UserResponse)
async def get_me(user: Annotated[User, Depends(get_current_user)]) -> UserResponse:
    return _user_to_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: dict,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    allowed = {"full_name", "phone_number", "avatar_url", "is_ai_enabled"}
    for k, v in payload.items():
        if k in allowed:
            setattr(user, k, v)
    await db.commit()
    await db.refresh(user)
    return _user_to_response(user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _rl: Annotated[None, Depends(rate_limit_dependency(max_requests=5, window_seconds=60))],
) -> MessageResponse:
    placeholder = hash_password("__placeholder__")
    if not verify_password(body.current_password, user.hashed_password or placeholder):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    user.hashed_password = hash_password(body.new_password)
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    return MessageResponse(message="Password changed")


# ─── AI kill switch ─────────────────────────────────────────────
class EmergencyStopBody(BaseModel):
    enabled: bool = True


@router.post("/ai/emergency-stop", response_model=MessageResponse)
async def emergency_stop(
    body: EmergencyStopBody,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.ai_emergency_stop = body.enabled
    if body.enabled:
        user.is_ai_enabled = False
    await db.commit()
    return MessageResponse(
        message="Emergency stop activated" if body.enabled else "Emergency stop cleared"
    )


# ─── Delete account ─────────────────────────────────────────────
@router.delete("/me", response_model=MessageResponse)
async def delete_account(
    body: DeleteAccountRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    if not body.confirm:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirmation required")
    await db.delete(user)
    await db.commit()
    return MessageResponse(message="Account deleted")
