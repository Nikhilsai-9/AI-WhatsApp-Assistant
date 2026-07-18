"""User settings model — global and per-contact preferences."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDMixin


class ReplyMode(str, enum.Enum):
    AUTO = "auto"          # AI replies automatically
    MANUAL = "manual"      # Owner must approve each reply
    SCHEDULED = "scheduled"  # Follow office hours / vacation rules


class ReplyDelay(str, enum.Enum):
    INSTANT = "instant"    # 0 seconds
    FAST = "fast"          # 5-15 seconds
    NORMAL = "normal"      # 30-90 seconds
    SLOW = "slow"          # 2-5 minutes


class UserSettings(UUIDMixin, Base):
    """Global settings for the owner."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # ─── AI Control ─────────────────────────────────────────────
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_reply_delay: Mapped[int] = mapped_column(Integer, default=0)

    # ─── Appearance ─────────────────────────────────────────────
    theme: Mapped[str] = mapped_column(String(20), default="light")

    # ─── Reply behaviour ────────────────────────────────────────
    reply_mode: Mapped[ReplyMode] = mapped_column(
        Enum(ReplyMode, name="reply_mode_enum", create_type=False),
        default=ReplyMode.AUTO,
        nullable=False,
    )
    reply_delay: Mapped[ReplyDelay] = mapped_column(
        Enum(ReplyDelay, name="reply_delay_enum", create_type=False),
        default=ReplyDelay.NORMAL,
        nullable=False,
    )
    reply_delay_seconds: Mapped[int] = mapped_column(default=60)

    # ─── Language / style ───────────────────────────────────────
    preferred_language: Mapped[str] = mapped_column(String(20), default="teluglish")
    generate_voice_replies: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_reply_voice: Mapped[str] = mapped_column(String(50), default="en-IN-NeerjaNeural")

    # ─── Smart filters ──────────────────────────────────────────
    filter_otps: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_bank_messages: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_spam: Mapped[bool] = mapped_column(Boolean, default=True)
    filter_promotions: Mapped[bool] = mapped_column(Boolean, default=True)

    # ─── Scheduled modes ────────────────────────────────────────
    silent_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    silent_start: Mapped[str | None] = mapped_column(String(5), default=None)  # "22:00"
    silent_end: Mapped[str | None] = mapped_column(String(5), default=None)    # "08:00"
    office_hours_only: Mapped[bool] = mapped_column(Boolean, default=False)
    office_start: Mapped[str] = mapped_column(String(5), default="09:00")
    office_end: Mapped[str] = mapped_column(String(5), default="18:00")
    vacation_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    vacation_message: Mapped[str | None] = mapped_column(String(500), default=None)

    # ─── AI settings ────────────────────────────────────────────
    ai_provider: Mapped[str] = mapped_column(String(50), default="gemini")
    ai_model: Mapped[str] = mapped_column(String(100), default="gemini-1.5-flash")
    ai_temperature: Mapped[float] = mapped_column(default=0.7)
    ai_max_tokens: Mapped[int] = mapped_column(default=500)

    # ─── Memory ─────────────────────────────────────────────────
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    memory_max_items: Mapped[int] = mapped_column(default=10000)
    memory_compression_threshold: Mapped[int] = mapped_column(default=5000)

    # ─── Notifications ──────────────────────────────────────────
    notify_on_approval_request: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_new_contact: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_error: Mapped[bool] = mapped_column(Boolean, default=True)

    # ─── Relationships ──────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="settings")