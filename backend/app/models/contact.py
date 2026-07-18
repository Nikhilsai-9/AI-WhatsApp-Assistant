"""Contact model — a WhatsApp person the owner has interacted with."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat import Chat
    from app.models.personality import PersonalityProfile


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"      # New contact, awaiting YES/NO
    APPROVED = "approved"    # Contact said YES
    DENIED = "denied"        # Contact said NO
    BLOCKED = "blocked"      # Owner manually blocked


class Contact(UUIDMixin, TimestampMixin, Base):
    """
    Represents a WhatsApp contact (person) the owner has chatted with.

    The bot ONLY operates on contacts with consent == APPROVED.
    """

    __tablename__ = "contacts"
    __table_args__ = (
        Index("ix_contacts_user_jid", "user_id", "whatsapp_jid", unique=True),
        Index("ix_contacts_whatsapp_jid", "whatsapp_jid"),
        Index("ix_contacts_user_consent", "user_id", "consent_status"),
        Index("ix_contacts_user_blacklist", "user_id", "is_blacklisted"),
        Index("ix_contacts_last_seen", "last_seen_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # WhatsApp JID (e.g. "919876543210@s.whatsapp.net")
    whatsapp_jid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Display name (from WhatsApp contact list)
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)

    # First seen / last seen
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Consent
    consent_status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, name="consent_status_enum", create_type=False),
        default=ConsentStatus.PENDING,
        nullable=False,
    )
    consent_given_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationship type (learned over time)
    relationship_type: Mapped[str | None] = mapped_column(
        String(50), default=None
    )  # "friend", "family", "colleague", "client", "teacher", etc.

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Manual overrides
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ─── Relationships ──────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="contacts")
    chats: Mapped[list["Chat"]] = relationship(
        "Chat", back_populates="contact", cascade="all, delete-orphan"
    )
    personality: Mapped["PersonalityProfile | None"] = relationship(
        "PersonalityProfile",
        back_populates="contact",
        uselist=False,
        cascade="all, delete-orphan",
    )