"""
Migration 003 — AI pause flag + ``chat_restrictions`` table.

Idempotent: every operation is guarded by an information_schema /
``pg_indexes`` lookup so running it twice is a no-op. Safe on both
fresh databases and existing ones that already started the schema in
002.

Revision ID: 003
Revises: 002
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "003"
down_revision: str | None = "002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t"
        ),
        {"t": table},
    ).first()
    return row is not None


def _index_exists(table: str, index_name: str) -> bool:
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM pg_indexes "
            "WHERE tablename = :t AND indexname = :i"
        ),
        {"t": table, "i": index_name},
    ).first()
    return row is not None


def upgrade() -> None:
    # 1) ``is_ai_paused`` on the ``users`` table (idempotent).
    if not _column_exists("users", "is_ai_paused"):
        op.add_column(
            "users",
            sa.Column(
                "is_ai_paused",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
        )

    # 2) ``chat_restrictions`` table — only create if missing. Uses raw
    #    SQL because alembic's ``create_table`` would fail loudly on the
    #    second run, which we explicitly want to support.
    if not _table_exists("chat_restrictions"):
        op.create_table(
            "chat_restrictions",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("uuid_generate_v4()"),
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("jid", sa.String(100), nullable=False),
            sa.Column(
                "mode",
                sa.String(20),
                nullable=False,
                server_default="ignored",
            ),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    if not _index_exists("chat_restrictions", "ix_chat_restrictions_user_id"):
        op.create_index(
            "ix_chat_restrictions_user_id",
            "chat_restrictions",
            ["user_id"],
        )
    if not _index_exists("chat_restrictions", "ix_chat_restrictions_jid"):
        op.create_index(
            "ix_chat_restrictions_jid",
            "chat_restrictions",
            ["jid"],
        )


def downgrade() -> None:
    op.drop_index("ix_chat_restrictions_jid", table_name="chat_restrictions")
    op.drop_index("ix_chat_restrictions_user_id", table_name="chat_restrictions")
    op.drop_table("chat_restrictions")
    op.drop_column("users", "is_ai_paused")