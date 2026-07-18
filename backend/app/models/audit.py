"""Audit log — immutable record of all owner actions."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """
    Immutable audit trail for owner actions.

    Records: login, settings changes, contact approvals, manual overrides, etc.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_action", "user_id", "action"),
        Index("ix_audit_created_at", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Examples: "login", "logout", "contact_approved", "contact_blocked",
    #           "settings_updated", "ai_paused", "ai_resumed", "memory_deleted"

    resource_type: Mapped[str | None] = mapped_column(String(50), default=None)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), default=None)

    # Snapshot of state before/after change
    detail: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)
    user_agent: Mapped[str | None] = mapped_column(String(500), default=None)

    # ─── Relationships ──────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="audit_logs")