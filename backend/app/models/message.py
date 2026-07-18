"""Message model — every WhatsApp message ever received/sent."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class MessageType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    GIF = "gif"
    LOCATION = "location"
    CONTACT = "contact"
    SYSTEM = "system"
    REACTION = "reaction"


class MessageDirection(str, enum.Enum):
    INCOMING = "incoming"   # from contact to owner
    OUTGOING = "outgoing"   # from owner (or AI) to contact


class Message(UUIDMixin, Base):
    """
    A single WhatsApp message.

    Both incoming (contact → owner) and outgoing (owner/AI → contact) are stored.
    """

    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_chat_id_timestamp", "chat_id", "timestamp"),
        Index("ix_messages_whatsapp_id", "whatsapp_message_id", unique=True),
        Index("ix_messages_direction", "direction"),
        Index("ix_messages_ai_reply", "is_ai_reply"),
        Index("ix_messages_chat_direction", "chat_id", "direction"),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )

    # WhatsApp's native message ID
    whatsapp_message_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )

    direction: Mapped[MessageDirection] = mapped_column(
        Enum(MessageDirection, name="message_direction_enum"),
        nullable=False,
    )

    message_type: Mapped[MessageType] = mapped_column(
        Enum(MessageType, name="message_type_enum"),
        default=MessageType.TEXT,
        nullable=False,
    )

    # When the message was sent on WhatsApp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Text content (null for media-only messages)
    text_content: Mapped[str | None] = mapped_column(Text, default=None)

    # Media
    media_url: Mapped[str | None] = mapped_column(String(500), default=None)
    media_mime_type: Mapped[str | None] = mapped_column(String(100), default=None)
    media_caption: Mapped[str | None] = mapped_column(Text, default=None)
    media_size_bytes: Mapped[int | None] = mapped_column(Integer, default=None)

    # OCR / transcription results
    ocr_text: Mapped[str | None] = mapped_column(Text, default=None)
    transcription: Mapped[str | None] = mapped_column(Text, default=None)

    # Sender identity
    sender_jid: Mapped[str | None] = mapped_column(String(100), default=None)

    # AI processing metadata
    is_ai_reply: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_reply_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), default=None
    )
    ai_confidence: Mapped[float | None] = mapped_column(default=None)

    # Smart filter
    is_filtered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    filter_reason: Mapped[str | None] = mapped_column(String(100), default=None)

    # Read status
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ─── Relationships ──────────────────────────────────────────
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")