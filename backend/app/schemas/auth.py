"""Auth schemas — request/response payloads for the auth API."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ─── Requests ─────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=255)
    phone_number: str | None = Field(None, max_length=30)


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class GoogleAuthRequest(BaseModel):
    id_token: str | None = None
    access_token: str | None = None

    def has_any(self) -> bool:
        return bool(self.id_token or self.access_token)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8, max_length=128)


class DeleteAccountRequest(BaseModel):
    confirm: bool


# ─── Responses ────────────────────────────────────────────────────
class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str | None = None
    phone_number: str | None = None
    avatar_url: str | None = None
    is_active: bool = True
    is_verified: bool = False
    email_verified: bool = False
    is_ai_enabled: bool = True
    ai_emergency_stop: bool = False
    created_at: datetime
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenPayload(BaseModel):
    sub: str
    exp: int
    type: str = "access"


class MessageResponse(BaseModel):
    message: str
    success: bool = True
