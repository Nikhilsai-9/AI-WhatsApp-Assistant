"""User model — account owners of the assistant."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.settings import UserSettings
    from app.models.audit import AuditLog


class User(UUIDMixin, TimestampMixin, Base):
    """One account per registered user."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # bcrypt hash — empty string allowed for OAuth-only users.
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    full_name: Mapped[str | None] = mapped_column(String(255), default=None)
    phone_number: Mapped[str | None] = mapped_column(String(30), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)

    # WhatsApp identity (optional)
    whatsapp_jid: Mapped[str | None] = mapped_column(
        String(100), unique=True, index=True, nullable=True
    )

    # Account state
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Auth bookkeeping
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Email verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Password reset
    password_reset_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    password_reset_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Emergency kill switch (logical AI panic stop)
    ai_emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ─── Relationships ──────────────────────────────────────────
    settings: Mapped["UserSettings"] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email}>"
