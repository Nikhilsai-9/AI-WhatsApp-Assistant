"""Dashboard schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DashboardStats(BaseModel):
    total_contacts: int
    approved_contacts: int
    pending_contacts: int
    blocked_contacts: int
    messages_today: int
    messages_this_week: int
    ai_replies_today: int
    memory_items: int
    learning_progress: float  # 0-100


class ActivitySummary(BaseModel):
    date: str
    incoming: int
    outgoing: int
    ai_replies: int


class ContactSummary(BaseModel):
    id: str
    display_name: str | None
    whatsapp_jid: str
    message_count: int
    last_message_at: datetime | None
    consent_status: str
    is_favorite: bool