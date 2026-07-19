"""Memory model — vector-backed long-term memory for the AI."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TimestampMixin, UUIDMixin


class MemoryType(str, enum.Enum):
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"   # specific events / conversations
    SEMANTIC = "semantic"   # facts, preferences, relationships
    WORKING = "working"     # current conversation context


class Memory(UUIDMixin, TimestampMixin, Base):
    """
    A stored memory unit with vector embedding for semantic search.

    Memories are created from processed messages and are the core of
    the AI's ability to recall context across conversations.
    """

    __tablename__ = "memories"
    # NOTE on index idempotency:
    # ``postgresql_if_not_exists`` is an *alembic-only* kwarg that is NOT
    # accepted by the model-level ``sqlalchemy.Index(...)`` constructor
    # (raises ``ArgumentError`` at import time and crashes Alembic).
    # Idempotency of these indexes is handled inside the migration scripts
    # via ``op.create_index(..., postgresql_if_not_exists=True)``.
    __table_args__ = (
        # pgvector HNSW index for semantic similarity search
        Index(
            "ix_memories_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"dims": 384, "m": 16, "ef_construction": 64},
        ),
        Index("ix_memories_contact_type", "contact_id", "memory_type"),
        Index("ix_memories_importance", "importance_score"),
    )

    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True
    )

    # Vector embedding (384-dim by default, configurable)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500), default=None)

    memory_type: Mapped[MemoryType] = mapped_column(
        Enum(MemoryType, name="memory_type_enum", create_type=False),
        default=MemoryType.LONG_TERM,
        nullable=False,
    )

    # Importance 0-10 (used for memory compression / eviction)
    importance_score: Mapped[float] = mapped_column(
        Float, default=5.0, nullable=False
    )

    # Access tracking
    access_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Source tracking
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )

    # Metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Soft expiry (for short-term / working memory)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ─── Relationships ──────────────────────────────────────────
    contact: Mapped["Contact | None"] = relationship("Contact", back_populates=None)
