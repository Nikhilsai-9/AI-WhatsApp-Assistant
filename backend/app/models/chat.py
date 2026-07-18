"""Chat model — a conversation thread with a specific contact."""

from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChatType(str, enum.Enum):
    INDIVIDUAL = "individual"
    GROUP = "group"          # intentionally ignored
    BROADCAST = "broadcast"  # intentionally ignored
    CHANNEL = "channel"      # intentionally ignored


class Chat(UUIDMixin, TimestampMixin, Base):
    """
    A WhatsApp chat thread.

    Only INDIVIDUAL chats are processed by the bot.
    """

    __tablename__ = "chats"
    __table_args__ = (
        Index("ix_chats_contact_id", "contact_id"),
        Index("ix_chats_whatsapp_id", "whatsapp_chat_id", unique=True),
    )

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )

    # WhatsApp's native chat ID
    whatsapp_chat_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    chat_type: Mapped[ChatType] = mapped_column(
        Enum(ChatType, name="chat_type_enum"),
        default=ChatType.INDIVIDUAL,
        nullable=False,
    )

    # Snapshot of contact name at time of creation
    subject: Mapped[str | None] = mapped_column(String(255), default=None)

    # Unread count
    unread_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # ─── Relationships ──────────────────────────────────────────
    contact: Mapped["Contact"] = relationship("Contact", back_populates="chats")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="chat",
        cascade="all, delete-orphan",
        order_by="Message.timestamp",
    )