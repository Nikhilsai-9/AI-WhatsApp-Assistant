"""
Migration 002 — adds authentication / OAuth fields to the `users` table.

This migration is **idempotent**: every operation is guarded by an
information_schema lookup so running it twice (e.g. on a redeploy with
no new schema) is a no-op.

Revision ID: 002
Revises: 001
Create Date: 2026-07-19
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: str | None = "001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _column_exists(table: str, column: str) -> bool:
    """Return True if *table*.*column* already exists."""
    bind = op.get_bind()
    row = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def upgrade() -> None:
    # Add each column only if it doesn't already exist.
    if not _column_exists("users", "avatar_url"):
        op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    if not _column_exists("users", "is_verified"):
        op.add_column(
            "users",
            sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        )
    if not _column_exists("users", "is_ai_enabled"):
        op.add_column(
            "users",
            sa.Column("is_ai_enabled", sa.Boolean, nullable=False, server_default="true"),
        )
    if not _column_exists("users", "token_version"):
        op.add_column(
            "users",
            sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
        )
    if not _column_exists("users", "email_verified"):
        op.add_column(
            "users",
            sa.Column("email_verified", sa.Boolean, nullable=False, server_default="false"),
        )
    if not _column_exists("users", "email_verification_token"):
        op.add_column(
            "users",
            sa.Column("email_verification_token", sa.String(500), nullable=True),
        )
    if not _column_exists("users", "password_reset_token"):
        op.add_column(
            "users",
            sa.Column("password_reset_token", sa.String(500), nullable=True),
        )
    if not _column_exists("users", "password_reset_expires"):
        op.add_column(
            "users",
            sa.Column("password_reset_expires", sa.DateTime(timezone=True), nullable=True),
        )
    if not _column_exists("users", "ai_emergency_stop"):
        op.add_column(
            "users",
            sa.Column("ai_emergency_stop", sa.Boolean, nullable=False, server_default="false"),
        )

    # `hashed_password` was NOT NULL in the original migration; for OAuth users
    # we now allow an empty string. Use a safe DO-block to relax it.
    op.execute(
        "DO $$\n"
        "BEGIN\n"
        "    IF EXISTS (\n"
        "        SELECT 1 FROM information_schema.columns\n"
        "        WHERE table_name = 'users' AND column_name = 'hashed_password'\n"
        "          AND is_nullable = 'NO'\n"
        "    ) THEN\n"
        "        ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;\n"
        "    END IF;\n"
        "END $$;"
    )


def downgrade() -> None:
    for col in (
        "ai_emergency_stop",
        "password_reset_expires",
        "password_reset_token",
        "email_verification_token",
        "email_verified",
        "token_version",
        "is_ai_enabled",
        "is_verified",
        "avatar_url",
    ):
        if _column_exists("users", col):
            op.drop_column("users", col)