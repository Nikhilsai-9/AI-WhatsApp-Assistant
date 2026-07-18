"""Personality profile — learned communication style per contact."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PersonalityProfile(UUIDMixin, TimestampMixin, Base):
    """
    Per-contact communication style profile.

    Built over time by analyzing the owner's sent messages to this contact.
    """

    __tablename__ = "personality_profiles"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # ─── Vocabulary ─────────────────────────────────────────────
    common_words: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # top-100 words used
    common_phrases: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # idioms, catchphrases
    slang: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # ─── Style ──────────────────────────────────────────────────
    avg_sentence_length: Mapped[float] = mapped_column(default=12.0)
    emoji_frequency: Mapped[float] = mapped_column(
        default=0.0
    )  # emojis per message
    common_emojis: Mapped[list[str]] = mapped_column(JSONB, default=list)
    caps_usage: Mapped[float] = mapped_column(
        default=0.0
    )  # fraction of messages with caps
    exclamation_usage: Mapped[float] = mapped_column(default=0.0)

    # ─── Greetings / Endings ────────────────────────────────────
    greeting_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    ending_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list)

    # ─── Language ───────────────────────────────────────────────
    primary_language: Mapped[str] = mapped_column(String(20), default="en")
    language_mixing: Mapped[list[str]] = mapped_column(
        JSONB, default=list
    )  # ["telugu", "english"]
    code_switching_pattern: Mapped[str | None] = mapped_column(
        String(50), default=None
    )  # "teluglish", "hinglish"

    # ─── Tone ───────────────────────────────────────────────────
    formality_score: Mapped[float] = mapped_column(
        default=0.5
    )  # 0=casual, 1=formal
    warmth_score: Mapped[float] = mapped_column(default=0.5)
    humor_score: Mapped[float] = mapped_column(default=0.5)
    professionalism_score: Mapped[float] = mapped_column(default=0.5)

    # ─── Learned context ────────────────────────────────────────
    relationship_type: Mapped[str | None] = mapped_column(String(50), default=None)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # ─── Confidence ─────────────────────────────────────────────
    message_count: Mapped[int] = mapped_column(default=0)
    confidence: Mapped[float] = mapped_column(default=0.0)  # 0-1

    # ─── Relationships ──────────────────────────────────────────
    contact: Mapped["Contact"] = relationship("Contact", back_populates="personality")