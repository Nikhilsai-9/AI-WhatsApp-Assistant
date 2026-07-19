"""Chat restriction model — per-chat AI behaviour overrides."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ChatRestriction(UUIDMixin, TimestampMixin, Base):
    """How the AI should treat a particular WhatsApp chat for one user."""

    __tablename__ = "chat_restrictions"

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    jid: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ignored")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="chat_restrictions")
