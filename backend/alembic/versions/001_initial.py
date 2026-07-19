"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-12

NOTE on idempotency:
    This migration is designed to be safely re-runnable. Every table
    creation is guarded by ``_create_table_if_not_exists`` and every
    index creation uses ``postgresql_if_not_exists=True``. Enum types
    are created via a ``DO`` block that skips when the type already
    exists. This makes the migration safe against:
      - partially-applied previous runs (e.g. a deploy that crashed
        after creating the enums but before finishing the tables)
      - fully-applied previous runs (every op is a no-op)
      - fresh databases (every op runs normally)
"""
from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import VECTOR

revision: str = "001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


# ── Idempotency helpers ────────────────────────────────────────
def _table_exists(name: str) -> bool:
    """Return True if a public table with this name already exists.

    PostgreSQL does NOT support ``CREATE TABLE IF NOT EXISTS`` natively,
    so we check ``information_schema.tables`` and skip if the table is
    already present. This prevents the ``DuplicateObject`` crash on a
    partially-applied previous migration run.
    """
    conn = op.get_bind()
    row = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = :n"
        ),
        {"n": name},
    ).first()
    return row is not None


def _create_table_if_not_exists(name: str, *columns, **kwargs) -> None:
    """Create a table only if it doesn't already exist."""
    if _table_exists(name):
        return
    op.create_table(name, *columns, **kwargs)


def _create_index_if_not_exists(name: str, table: str, columns, **kwargs) -> None:
    """Create a PostgreSQL index only if it doesn't already exist.

    Uses the postgres-only ``postgresql_if_not_exists=True`` kwarg so
    that re-running this migration on a DB where the index already
    exists is a no-op (avoids ``DuplicateTable`` for indexes).
    """
    kwargs.setdefault("postgresql_if_not_exists", True)
    op.create_index(name, table, columns, **kwargs)


def _create_enum(name: str, values: str) -> None:
    """Create a PostgreSQL ENUM type, skipping if it already exists.

    PostgreSQL does NOT support ``CREATE TYPE IF NOT EXISTS`` natively,
    so we wrap the create in a ``DO`` block that checks ``pg_type``
    first. This makes enum creation idempotent across re-deploys.
    """
    op.execute(
        "DO $do$\n"
        "BEGIN\n"
        f"    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN\n"
        f"        CREATE TYPE {name} AS ENUM ({values});\n"
        "    END IF;\n"
        "END\n"
        "$do$;"
    )


def upgrade() -> None:
    # ─── extensions ─────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ─── enums (idempotent) ─────────────────────────────────────
    _create_enum("consent_status_enum",
                 "'pending','approved','denied','blocked'")
    _create_enum("chat_type_enum",
                 "'individual','group','broadcast','channel'")
    _create_enum("message_type_enum",
                 "'text','image','video','audio','voice','document',"
                 "'sticker','gif','location','contact','system','reaction'")
    _create_enum("message_direction_enum", "'incoming','outgoing'")
    _create_enum("memory_type_enum",
                 "'short_term','long_term','episodic','semantic','working'")
    _create_enum("reply_mode_enum", "'auto','manual','scheduled'")
    _create_enum("reply_delay_enum", "'instant','fast','normal','slow'")

    # ─── users ──────────────────────────────────────────────────
    _create_table_if_not_exists(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("whatsapp_jid", sa.String(100), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    _create_index_if_not_exists("ix_users_email", "users", ["email"], unique=True)
    _create_index_if_not_exists("ix_users_whatsapp_jid", "users", ["whatsapp_jid"], unique=True)

    # ─── contacts ───────────────────────────────────────────────
    _create_table_if_not_exists(
        "contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_jid", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("consent_status",
                  sa.Enum("pending", "approved", "denied", "blocked",
                          name="consent_status_enum", create_type=False),
                  nullable=False, server_default="pending"),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relationship_type", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_blacklisted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_favorite", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    _create_index_if_not_exists("ix_contacts_user_jid", "contacts",
                                ["user_id", "whatsapp_jid"], unique=True)
    _create_index_if_not_exists("ix_contacts_whatsapp_jid", "contacts",
                                ["whatsapp_jid"])

    # ─── chats ──────────────────────────────────────────────────
    _create_table_if_not_exists(
        "chats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True),
                  sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_chat_id", sa.String(100), unique=True, nullable=False),
        sa.Column("chat_type",
                  sa.Enum("individual", "group", "broadcast", "channel",
                          name="chat_type_enum", create_type=False),
                  nullable=False, server_default="individual"),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    _create_index_if_not_exists("ix_chats_contact_id", "chats", ["contact_id"])
    _create_index_if_not_exists("ix_chats_whatsapp_id", "chats",
                                ["whatsapp_chat_id"], unique=True)

    # ─── messages ───────────────────────────────────────────────
    _create_table_if_not_exists(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("chat_id", UUID(as_uuid=True),
                  sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_message_id", sa.String(100), unique=True, nullable=False),
        sa.Column("direction",
                  sa.Enum("incoming", "outgoing",
                          name="message_direction_enum", create_type=False),
                  nullable=False),
        sa.Column("message_type",
                  sa.Enum("text", "image", "video", "audio", "voice", "document",
                          "sticker", "gif", "location", "contact", "system",
                          "reaction", name="message_type_enum", create_type=False),
                  nullable=False, server_default="text"),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("text_content", sa.Text, nullable=True),
        sa.Column("media_url", sa.String(500), nullable=True),
        sa.Column("media_mime_type", sa.String(100), nullable=True),
        sa.Column("media_caption", sa.Text, nullable=True),
        sa.Column("media_size_bytes", sa.Integer, nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("transcription", sa.Text, nullable=True),
        sa.Column("sender_jid", sa.String(100), nullable=True),
        sa.Column("is_ai_reply", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_reply_id", UUID(as_uuid=True), nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("is_filtered", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("filter_reason", sa.String(100), nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
    )
    _create_index_if_not_exists("ix_messages_chat_id_timestamp", "messages",
                                ["chat_id", "timestamp"])
    _create_index_if_not_exists("ix_messages_whatsapp_id", "messages",
                                ["whatsapp_message_id"], unique=True)
    _create_index_if_not_exists("ix_messages_direction", "messages",
                                ["direction"])

    # ─── memories ───────────────────────────────────────────────
    _create_table_if_not_exists(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True),
                  sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("memory_type",
                  sa.Enum("short_term", "long_term", "episodic", "semantic",
                          "working", name="memory_type_enum", create_type=False),
                  nullable=False, server_default="long_term"),
        sa.Column("importance_score", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_message_id", UUID(as_uuid=True),
                  sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    _create_index_if_not_exists("ix_memories_contact_type", "memories",
                                ["contact_id", "memory_type"])
    _create_index_if_not_exists("ix_memories_importance", "memories",
                                ["importance_score"])
    # pgvector HNSW index — must be created with `postgresql_if_not_exists`
    # at the alembic level (this kwarg is NOT valid on model-level Index()).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memories_embedding "
        "ON memories USING hnsw (embedding vector_cosine_ops) "
        "WITH (dims = 384, m = 16, ef_construction = 64)"
    )

    # ─── personality_profiles ───────────────────────────────────
    _create_table_if_not_exists(
        "personality_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True),
                  sa.ForeignKey("contacts.id", ondelete="CASCADE"),
                  unique=True, nullable=False),
        sa.Column("common_words", JSONB, nullable=True, server_default="[]"),
        sa.Column("common_phrases", JSONB, nullable=True, server_default="[]"),
        sa.Column("slang", JSONB, nullable=True, server_default="[]"),
        sa.Column("avg_sentence_length", sa.Float, nullable=False, server_default="12.0"),
        sa.Column("emoji_frequency", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("common_emojis", JSONB, nullable=True, server_default="[]"),
        sa.Column("caps_usage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("exclamation_usage", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("greeting_patterns", JSONB, nullable=True, server_default="[]"),
        sa.Column("ending_patterns", JSONB, nullable=True, server_default="[]"),
        sa.Column("primary_language", sa.String(20), nullable=False, server_default="en"),
        sa.Column("language_mixing", JSONB, nullable=True, server_default="[]"),
        sa.Column("code_switching_pattern", sa.String(50), nullable=True),
        sa.Column("formality_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("warmth_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("humor_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("professionalism_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("relationship_type", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("message_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ─── user_settings ──────────────────────────────────────────
    _create_table_if_not_exists(
        "user_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  unique=True, nullable=False),
        sa.Column("reply_mode",
                  sa.Enum("auto", "manual", "scheduled",
                          name="reply_mode_enum", create_type=False),
                  nullable=False, server_default="auto"),
        sa.Column("reply_delay",
                  sa.Enum("instant", "fast", "normal", "slow",
                          name="reply_delay_enum", create_type=False),
                  nullable=False, server_default="normal"),
        sa.Column("reply_delay_seconds", sa.Integer, nullable=False, server_default="60"),
        sa.Column("preferred_language", sa.String(20), nullable=False,
                  server_default="teluglish"),
        sa.Column("generate_voice_replies", sa.Boolean, nullable=False,
                  server_default="false"),
        sa.Column("voice_reply_voice", sa.String(50), nullable=False,
                  server_default="en-IN-NeerjaNeural"),
        sa.Column("filter_otps", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("filter_bank_messages", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("filter_spam", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("filter_promotions", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("silent_mode", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("silent_start", sa.String(5), nullable=True),
        sa.Column("silent_end", sa.String(5), nullable=True),
        sa.Column("office_hours_only", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("office_start", sa.String(5), nullable=False, server_default="09:00"),
        sa.Column("office_end", sa.String(5), nullable=False, server_default="18:00"),
        sa.Column("vacation_mode", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vacation_message", sa.String(500), nullable=True),
        sa.Column("ai_provider", sa.String(50), nullable=False, server_default="gemini"),
        sa.Column("ai_model", sa.String(100), nullable=False,
                  server_default="gemini-1.5-flash"),
        sa.Column("ai_temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("ai_max_tokens", sa.Integer, nullable=False, server_default="500"),
        sa.Column("memory_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("memory_max_items", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("memory_compression_threshold", sa.Integer, nullable=False,
                  server_default="5000"),
        sa.Column("notify_on_approval_request", sa.Boolean, nullable=False,
                  server_default="true"),
        sa.Column("notify_on_new_contact", sa.Boolean, nullable=False,
                  server_default="true"),
        sa.Column("notify_on_error", sa.Boolean, nullable=False, server_default="true"),
    )

    # ─── audit_logs ─────────────────────────────────────────────
    _create_table_if_not_exists(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("detail", JSONB, nullable=True, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    _create_index_if_not_exists("ix_audit_user_action", "audit_logs",
                                ["user_id", "action"])
    _create_index_if_not_exists("ix_audit_created_at", "audit_logs",
                                ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("user_settings")
    op.drop_table("personality_profiles")
    op.drop_table("memories")
    op.drop_table("messages")
    op.drop_table("chats")
    op.drop_table("contacts")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS reply_delay_enum")
    op.execute("DROP TYPE IF EXISTS reply_mode_enum")
    op.execute("DROP TYPE IF EXISTS memory_type_enum")
    op.execute("DROP TYPE IF EXISTS message_direction_enum")
    op.execute("DROP TYPE IF EXISTS message_type_enum")
    op.execute("DROP TYPE IF EXISTS chat_type_enum")
    op.execute("DROP TYPE IF EXISTS consent_status_enum")
