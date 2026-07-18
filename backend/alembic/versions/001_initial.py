"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-12
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


def upgrade() -> None:
    # ─── extensions ─────────────────────────────────────────────
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ─── enums ──────────────────────────────────────────────────
    op.execute("CREATE TYPE consent_status_enum AS ENUM ('pending','approved','denied','blocked')")
    op.execute("CREATE TYPE chat_type_enum AS ENUM ('individual','group','broadcast','channel')")
    op.execute("CREATE TYPE message_type_enum AS ENUM ('text','image','video','audio','voice','document','sticker','gif','location','contact','system','reaction')")
    op.execute("CREATE TYPE message_direction_enum AS ENUM ('incoming','outgoing')")
    op.execute("CREATE TYPE memory_type_enum AS ENUM ('short_term','long_term','episodic','semantic','working')")
    op.execute("CREATE TYPE reply_mode_enum AS ENUM ('auto','manual','scheduled')")
    op.execute("CREATE TYPE reply_delay_enum AS ENUM ('instant','fast','normal','slow')")

    # ─── users ──────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(30), nullable=True),
        sa.Column("whatsapp_jid", sa.String(100), unique=True, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_whatsapp_jid", "users", ["whatsapp_jid"], unique=True)

    # ─── contacts ───────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_jid", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("consent_status", sa.Enum("pending","approved","denied","blocked", name="consent_status_enum"), nullable=False, server_default="pending"),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("relationship_type", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_blacklisted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_favorite", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_contacts_user_jid", "contacts", ["user_id","whatsapp_jid"], unique=True)
    op.create_index("ix_contacts_whatsapp_jid", "contacts", ["whatsapp_jid"])

    # ─── chats ──────────────────────────────────────────────────
    op.create_table(
        "chats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_chat_id", sa.String(100), unique=True, nullable=False),
        sa.Column("chat_type", sa.Enum("individual","group","broadcast","channel", name="chat_type_enum"), nullable=False, server_default="individual"),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("unread_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_chats_contact_id", "chats", ["contact_id"])
    op.create_index("ix_chats_whatsapp_id", "chats", ["whatsapp_chat_id"], unique=True)

    # ─── messages ───────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("chat_id", UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("whatsapp_message_id", sa.String(100), unique=True, nullable=False),
        sa.Column("direction", sa.Enum("incoming","outgoing", name="message_direction_enum"), nullable=False),
        sa.Column("message_type", sa.Enum("text","image","video","audio","voice","document","sticker","gif","location","contact","system","reaction", name="message_type_enum"), nullable=False, server_default="text"),
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
    op.create_index("ix_messages_chat_id_timestamp", "messages", ["chat_id","timestamp"])
    op.create_index("ix_messages_whatsapp_id", "messages", ["whatsapp_message_id"], unique=True)
    op.create_index("ix_messages_direction", "messages", ["direction"])

    # ─── memories ───────────────────────────────────────────────
    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("embedding", VECTOR(384), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("memory_type", sa.Enum("short_term","long_term","episodic","semantic","working", name="memory_type_enum"), nullable=False, server_default="long_term"),
        sa.Column("importance_score", sa.Float, nullable=False, server_default="5.0"),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True, server_default="{}"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_memories_contact_type", "memories", ["contact_id","memory_type"])
    op.create_index("ix_memories_importance", "memories", ["importance_score"])

    # ─── personality_profiles ───────────────────────────────────
    op.create_table(
        "personality_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="CASCADE"), unique=True, nullable=False),
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # ─── user_settings ──────────────────────────────────────────
    op.create_table(
        "user_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("reply_mode", sa.Enum("auto","manual","scheduled", name="reply_mode_enum"), nullable=False, server_default="auto"),
        sa.Column("reply_delay", sa.Enum("instant","fast","normal","slow", name="reply_delay_enum"), nullable=False, server_default="normal"),
        sa.Column("reply_delay_seconds", sa.Integer, nullable=False, server_default="60"),
        sa.Column("preferred_language", sa.String(20), nullable=False, server_default="teluglish"),
        sa.Column("generate_voice_replies", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("voice_reply_voice", sa.String(50), nullable=False, server_default="en-IN-NeerjaNeural"),
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
        sa.Column("ai_model", sa.String(100), nullable=False, server_default="gemini-1.5-flash"),
        sa.Column("ai_temperature", sa.Float, nullable=False, server_default="0.7"),
        sa.Column("ai_max_tokens", sa.Integer, nullable=False, server_default="500"),
        sa.Column("memory_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("memory_max_items", sa.Integer, nullable=False, server_default="10000"),
        sa.Column("memory_compression_threshold", sa.Integer, nullable=False, server_default="5000"),
        sa.Column("notify_on_approval_request", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_on_new_contact", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notify_on_error", sa.Boolean, nullable=False, server_default="true"),
    )

    # ─── audit_logs ─────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=True),
        sa.Column("resource_id", UUID(as_uuid=True), nullable=True),
        sa.Column("detail", JSONB, nullable=True, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_audit_user_action", "audit_logs", ["user_id","action"])
    op.create_index("ix_audit_created_at", "audit_logs", ["created_at"])


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