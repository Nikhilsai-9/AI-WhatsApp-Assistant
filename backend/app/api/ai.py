"""
AI control endpoints.

Exposes the user-facing switches that the dashboard needs:

* ``GET    /ai/status``           — current AI state (enabled / paused / emergency)
* ``POST   /ai/enable``           — turn the AI back on
* ``POST   /ai/disable``          — permanently disable the AI
* ``POST   /ai/pause``            — pause replies (e.g. focus mode)
* ``POST   /ai/resume``           — resume from a pause
* ``POST   /ai/restart``          — restart the AI runtime / reload settings
* ``POST   /ai/emergency-kill``   — flip the panic switch
* ``POST   /ai/emergency-reset``  — reset the panic switch
* ``GET    /ai/chat-restrictions`` — chat restriction list
* ``PUT    /ai/chat-restrictions`` — replace chat restriction list
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.chat_restriction import ChatRestriction
from app.models.user import User
from app.schemas.auth import MessageResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


# ─── Request / Response payloads ─────────────────────────────────
class AIStatusResponse(BaseModel):
    is_ai_enabled: bool
    is_paused: bool
    ai_emergency_stop: bool
    mode: Literal["active", "disabled", "paused", "emergency_stop"]


class PauseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)


class ChatRestrictionPayload(BaseModel):
    jid: str
    mode: Literal["allowed", "ignored", "blocked", "restricted", "read_only", "muted"]
    notes: str | None = Field(default=None, max_length=500)


class ChatRestrictionListResponse(BaseModel):
    items: list[ChatRestrictionPayload]


# ─── Status & control ─────────────────────────────────────────────
@router.get("/status", response_model=AIStatusResponse)
async def ai_status(user: Annotated[User, Depends(get_current_user)]) -> AIStatusResponse:
    """Return the current AI status for the user."""
    if getattr(user, "ai_emergency_stop", False):
        mode = "emergency_stop"
    elif not getattr(user, "is_ai_enabled", True):
        mode = "disabled"
    elif getattr(user, "is_ai_paused", False):
        mode = "paused"
    else:
        mode = "active"
    return AIStatusResponse(
        is_ai_enabled=getattr(user, "is_ai_enabled", True),
        is_paused=getattr(user, "is_ai_paused", False),
        ai_emergency_stop=getattr(user, "ai_emergency_stop", False),
        mode=mode,
    )


@router.post("/enable", response_model=MessageResponse)
async def ai_enable(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.is_ai_enabled = True
    user.is_ai_paused = False
    user.ai_emergency_stop = False
    await db.commit()
    logger.info("ai_enabled", user_id=str(user.id))
    return MessageResponse(message="AI enabled")


@router.post("/disable", response_model=MessageResponse)
async def ai_disable(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.is_ai_enabled = False
    await db.commit()
    logger.info("ai_disabled", user_id=str(user.id))
    return MessageResponse(message="AI disabled")


@router.post("/pause", response_model=MessageResponse)
async def ai_pause(
    payload: PauseRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.is_ai_paused = True
    await db.commit()
    logger.info("ai_paused", user_id=str(user.id), reason=payload.reason)
    return MessageResponse(message="AI paused")


@router.post("/resume", response_model=MessageResponse)
async def ai_resume(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.is_ai_paused = False
    await db.commit()
    logger.info("ai_resumed", user_id=str(user.id))
    return MessageResponse(message="AI resumed")


@router.post("/restart", response_model=MessageResponse)
async def ai_restart(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    """Clear pause + emergency, bump token-version to force reload of settings."""
    user.is_ai_paused = False
    user.ai_emergency_stop = False
    user.is_ai_enabled = True
    user.token_version = (user.token_version or 0) + 1
    await db.commit()
    logger.info("ai_restarted", user_id=str(user.id))
    return MessageResponse(message="AI restarted")


@router.post("/emergency-kill", response_model=MessageResponse)
async def emergency_kill(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.ai_emergency_stop = True
    await db.commit()
    logger.warning("ai_emergency_kill", user_id=str(user.id))
    return MessageResponse(message="Emergency stop engaged")


@router.post("/emergency-reset", response_model=MessageResponse)
async def emergency_reset(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    user.ai_emergency_stop = False
    user.is_ai_paused = False
    user.is_ai_enabled = True
    await db.commit()
    logger.info("ai_emergency_reset", user_id=str(user.id))
    return MessageResponse(message="Emergency stop reset")


# ─── Chat restrictions ────────────────────────────────────────────
@router.get("/chat-restrictions", response_model=ChatRestrictionListResponse)
async def list_chat_restrictions(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatRestrictionListResponse:
    res = await db.execute(
        select(ChatRestriction).where(ChatRestriction.user_id == user.id)
    )
    items = [
        ChatRestrictionPayload(jid=r.jid, mode=r.mode, notes=r.notes)
        for r in res.scalars().all()
    ]
    return ChatRestrictionListResponse(items=items)


@router.put("/chat-restrictions", response_model=ChatRestrictionListResponse)
async def replace_chat_restrictions(
    payload: ChatRestrictionListResponse,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ChatRestrictionListResponse:
    res = await db.execute(
        select(ChatRestriction).where(ChatRestriction.user_id == user.id)
    )
    existing = {r.jid: r for r in res.scalars().all()}
    seen: set[str] = set()
    for item in payload.items:
        seen.add(item.jid)
        if item.jid in existing:
            row = existing[item.jid]
            row.mode = item.mode
            row.notes = item.notes
        else:
            db.add(
                ChatRestriction(
                    user_id=user.id, jid=item.jid, mode=item.mode, notes=item.notes
                )
            )
    # Delete rows that were removed
    for jid, row in existing.items():
        if jid not in seen:
            await db.delete(row)
    await db.commit()
    return payload
