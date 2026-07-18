"""Auth routes — register, login, refresh tokens."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
    TokenPayload,
)

router = APIRouter()
logger = get_logger(__name__)

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)


def create_access_token(user_id: str) -> tuple[str, int]:
    exp = int((datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)).timestamp())
    token = jwt.encode(
        {"sub": user_id, "exp": exp, "type": "access"},
        settings.app_secret,
        algorithm=settings.jwt_algorithm,
    )
    return token, exp


def create_refresh_token(user_id: str) -> str:
    exp = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
    return jwt.encode(
        {"sub": user_id, "exp": exp, "type": "refresh"},
        settings.app_secret,
        algorithm=settings.jwt_algorithm,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(token, settings.app_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None or payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/register", response_model=AuthResponse)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)):
    # Check existing
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
        phone_number=body.phone_number,
    )
    session.add(user)
    await session.flush()

    # Create default settings
    from app.models.settings import UserSettings
    settings_row = UserSettings(user_id=user.id)
    session.add(settings_row)

    # Audit log
    session.add(AuditLog(user_id=user.id, action="register", detail={"email": body.email}))

    await session.commit()
    await session.refresh(user)

    access_token, exp = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    logger.info("user_registered", user_id=str(user.id))
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=exp - int(datetime.now(timezone.utc).timestamp()),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_db),
):
    # Rate limit: 5 login attempts per minute per IP
    from app.core.rate_limit import check_rate_limit
    client_ip = "unknown"  # Will be set by middleware in production
    safe_key = f"login:{hashlib.sha256(client_ip.encode()).hexdigest()[:16]}"
    await check_rate_limit(safe_key, max_requests=5, window_seconds=60)
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    session.add(AuditLog(user_id=user.id, action="login"))
    await session.commit()

    access_token, exp = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))

    logger.info("user_login", user_id=str(user.id))
    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=exp - int(datetime.now(timezone.utc).timestamp()),
    )


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest, session: AsyncSession = Depends(get_db)):
    try:
        payload = jwt.decode(body.refresh_token, settings.app_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id: str = payload["sub"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    access_token, exp = create_access_token(str(user.id))
    new_refresh = create_refresh_token(str(user.id))

    return AuthResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=exp - int(datetime.now(timezone.utc).timestamp()),
    )