"""Message routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.chat import Chat
from app.models.contact import Contact
from app.models.message import Message
from app.models.user import User
from app.schemas.message import MessageResponse, ReplyRequest, ReplyResponse
from app.services.ai.client import AIService, ReplyContext, get_ai_service
from app.services.memory.engine import MemoryEngine, get_memory_engine

router = APIRouter()


@router.get("/chat/{chat_id}", response_model=list[MessageResponse])
async def get_chat_messages(
    chat_id: str,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Chat)
        .join(Chat.contact)
        .where(Chat.id == uuid.UUID(chat_id), Contact.user_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Chat not found")

    msg_result = await session.execute(
        select(Message)
        .where(Message.chat_id == uuid.UUID(chat_id))
        .order_by(Message.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    messages = list(reversed(msg_result.scalars().all()))
    return [MessageResponse.model_validate(m) for m in messages]


@router.post("/reply", response_model=ReplyResponse)
async def generate_reply(
    body: ReplyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    msg_result = await session.execute(
        select(Message)
        .where(Message.id == uuid.UUID(body.message_id))
        .options(selectinload(Message.chat).selectinload(Chat.contact))
    )
    msg = msg_result.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    contact = msg.chat.contact
    if contact.user_id != user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Override text if provided
    if body.override_text:
        return ReplyResponse(
            message_id=body.message_id,
            reply_text=body.override_text,
            confidence=1.0,
            reply_type=body.reply_type,
        )

    # Build context
    history_result = await session.execute(
        select(Message)
        .where(Message.chat_id == msg.chat_id)
        .order_by(Message.timestamp.desc())
        .limit(20)
    )
    history = list(reversed(history_result.scalars().all()))
    history_dicts = [
        {"direction": m.direction.value, "text": m.text_content or ""}
        for m in history[:-1]
    ]

    memory = get_memory_engine(session)
    memory_context = await memory.get_context_for_contact(contact.id)

    ctx = ReplyContext(
        incoming_message=msg.text_content or "",
        conversation_history=history_dicts,
        contact_name=contact.display_name,
        relationship_type=contact.relationship_type or "friend",
        memory_context=memory_context,
        reply_type=body.reply_type,
    )

    ai = get_ai_service()
    reply = await ai.generate_reply(ctx)

    return ReplyResponse(
        message_id=body.message_id,
        reply_text=reply.text,
        confidence=reply.confidence,
        reply_type=body.reply_type,
    )