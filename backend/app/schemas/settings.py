"""Settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    ai_enabled: bool | None = None
    auto_reply_delay: int | None = Field(None, ge=0, le=300)
    theme: str | None = None
    reply_mode: str | None = None
    reply_delay: str | None = None
    reply_delay_seconds: int | None = Field(None, ge=0, le=600)
    preferred_language: str | None = None
    generate_voice_replies: bool | None = None
    voice_reply_voice: str | None = None
    filter_otps: bool | None = None
    filter_bank_messages: bool | None = None
    filter_spam: bool | None = None
    filter_promotions: bool | None = None
    silent_mode: bool | None = None
    silent_start: str | None = None
    silent_end: str | None = None
    office_hours_only: bool | None = None
    office_start: str | None = None
    office_end: str | None = None
    vacation_mode: bool | None = None
    vacation_message: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_temperature: float | None = Field(None, ge=0.0, le=2.0)
    ai_max_tokens: int | None = Field(None, ge=1, le=4096)
    memory_enabled: bool | None = None
    memory_max_items: int | None = None
    notify_on_approval_request: bool | None = None
    notify_on_new_contact: bool | None = None
    notify_on_error: bool | None = None


class SettingsResponse(BaseModel):
    ai_enabled: bool
    auto_reply_delay: int
    theme: str
    reply_mode: str
    reply_delay: str
    reply_delay_seconds: int
    preferred_language: str
    generate_voice_replies: bool
    voice_reply_voice: str
    filter_otps: bool
    filter_bank_messages: bool
    filter_spam: bool
    filter_promotions: bool
    silent_mode: bool
    silent_start: str | None
    silent_end: str | None
    office_hours_only: bool
    office_start: str
    office_end: str
    vacation_mode: bool
    vacation_message: str | None
    ai_provider: str
    ai_model: str
    ai_temperature: float
    ai_max_tokens: int
    memory_enabled: bool
    memory_max_items: int
    notify_on_approval_request: bool
    notify_on_new_contact: bool
    notify_on_error: bool

    model_config = {"from_attributes": True}