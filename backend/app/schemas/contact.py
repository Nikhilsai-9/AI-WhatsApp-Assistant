"""Contact schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.contact import ConsentStatus


class ContactCreate(BaseModel):
    whatsapp_jid: str = Field(..., max_length=100)
    display_name: str | None = None


class ContactUpdate(BaseModel):
    display_name: str | None = None
    relationship_type: str | None = None
    notes: str | None = None
    is_favorite: bool | None = None


class ContactResponse(BaseModel):
    id: str
    whatsapp_jid: str
    display_name: str | None
    consent_status: ConsentStatus
    relationship_type: str | None
    notes: str | None
    is_blacklisted: bool
    is_favorite: bool
    first_seen_at: datetime
    last_seen_at: datetime
    message_count: int = 0
    last_message_at: datetime | None = None

    model_config = {"from_attributes": True}


class ConsentAction(BaseModel):
    contact_id: str
    action: str = Field(..., pattern="^(approve|deny|block|unblock)$")