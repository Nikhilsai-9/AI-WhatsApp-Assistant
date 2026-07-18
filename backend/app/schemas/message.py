"""Message schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.message import MessageDirection, MessageType


class MessageCreate(BaseModel):
    chat_id: str
    whatsapp_message_id: str
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime
    text_content: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    media_caption: str | None = None
    sender_jid: str | None = None


class MessageIngest(BaseModel):
    """Payload sent by the WhatsApp bridge for every incoming message."""

    whatsapp_message_id: str
    whatsapp_chat_id: str
    sender_jid: str
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    timestamp: datetime
    text_content: str | None = None
    media_url: str | None = None
    media_mime_type: str | None = None
    media_caption: str | None = None
    sender_name: str | None = None


class MessageResponse(BaseModel):
    id: str
    chat_id: str
    direction: MessageDirection
    message_type: MessageType
    timestamp: datetime
    text_content: str | None
    media_url: str | None
    ocr_text: str | None
    transcription: str | None
    is_ai_reply: bool
    is_filtered: bool
    filter_reason: str | None

    model_config = {"from_attributes": True}


class ReplyRequest(BaseModel):
    message_id: str
    override_text: str | None = None
    reply_type: str = Field(
        default="auto",
        pattern="^(auto|quick|detailed|professional|funny|short|long|voice)$",
    )


class ReplyResponse(BaseModel):
    message_id: str
    reply_text: str
    confidence: float
    reply_type: str
    queued: bool = False