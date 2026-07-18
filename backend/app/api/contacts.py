"""Contact management routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.audit import AuditLog
from app.models.contact import ConsentStatus, Contact
from app.models.message import Message
from app.models.user import User
from app.schemas.contact import ConsentAction, ContactResponse, ContactUpdate

router = APIRouter()
logger = get_logger(__name__)


@router.get("/", response_model=list[ContactResponse])
async def list_contacts(
    consent_status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    # Use single query with subqueries to avoid N+1
    from app.models.chat import Chat
    
    # Subquery for message counts
    msg_count_subq = (
        select(Message.chat_id, func.count(Message.id).label("msg_count"))
        .group_by(Message.chat_id)
        .subquery()
    )
    
    # Subquery for last message timestamps
    last_msg_subq = (
        select(
            Message.chat_id,
            func.max(Message.timestamp).label("last_msg_at")
        )
        .group_by(Message.chat_id)
        .subquery()
    )
    
    # Subquery for chat -> contact mapping
    chat_contact_subq = (
        select(Chat.id, Chat.contact_id)
        .subquery()
    )
    
    # Main query with joins
    stmt = (
        select(
            Contact,
            func.coalesce(msg_count_subq.c.msg_count, 0).label("message_count"),
            last_msg_subq.c.last_msg_at.label("last_message_at")
        )
        .outerjoin(chat_contact_subq, Contact.id == chat_contact_subq.c.contact_id)
        .outerjoin(msg_count_subq, chat_contact_subq.c.id == msg_count_subq.c.chat_id)
        .outerjoin(last_msg_subq, chat_contact_subq.c.id == last_msg_subq.c.chat_id)
        .where(Contact.user_id == user.id)
        .options(selectinload(Contact.personality))
        .order_by(Contact.last_seen_at.desc())
    )
    
    if consent_status:
        stmt = stmt.where(Contact.consent_status == consent_status)
    if search:
        stmt = stmt.where(Contact.display_name.ilike(f"%{search}%"))

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    rows = result.all()

    responses = []
    for row in rows:
        contact = row[0]
        msg_count = row[1] or 0
        last_msg = row[2]
        
        responses.append(
            ContactResponse(
                id=str(contact.id),
                whatsapp_jid=contact.whatsapp_jid,
                display_name=contact.display_name,
                consent_status=contact.consent_status,
                relationship_type=contact.relationship_type,
                notes=contact.notes,
                is_blacklisted=contact.is_blacklisted,
                is_favorite=contact.is_favorite,
                first_seen_at=contact.first_seen_at,
                last_seen_at=contact.last_seen_at,
                message_count=msg_count,
                last_message_at=last_msg,
            )
        )
    return responses


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Contact)
        .where(Contact.id == uuid.UUID(contact_id), Contact.user_id == user.id)
        .options(selectinload(Contact.personality))
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return ContactResponse.model_validate(contact)


@router.patch("/{contact_id}")
async def update_contact(
    contact_id: str,
    body: ContactUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Contact).where(Contact.id == uuid.UUID(contact_id), Contact.user_id == user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)

    session.add(AuditLog(user_id=user.id, action="contact_updated", resource_type="contact", resource_id=contact.id))
    await session.commit()
    return {"status": "ok"}


@router.post("/consent")
async def consent_action(
    body: ConsentAction,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Contact).where(Contact.id == uuid.UUID(body.contact_id), Contact.user_id == user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    match body.action:
        case "approve":
            contact.consent_status = ConsentStatus.APPROVED
            contact.consent_given_at = datetime.now(timezone.utc)
            action_log = "contact_approved"
        case "deny":
            contact.consent_status = ConsentStatus.DENIED
            action_log = "contact_denied"
        case "block":
            contact.is_blacklisted = True
            contact.consent_status = ConsentStatus.BLOCKED
            action_log = "contact_blocked"
        case "unblock":
            contact.is_blacklisted = False
            contact.consent_status = ConsentStatus.PENDING
            action_log = "contact_unblocked"

    session.add(AuditLog(user_id=user.id, action=action_log, resource_type="contact", resource_id=contact.id))
    await session.commit()
    logger.info(action_log, contact_id=body.contact_id)
    return {"status": "ok", "consent_status": contact.consent_status.value}


@router.delete("/{contact_id}")
async def delete_contact(
    contact_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    result = await session.execute(
        select(Contact).where(Contact.id == uuid.UUID(contact_id), Contact.user_id == user.id)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    await session.delete(contact)
    session.add(AuditLog(user_id=user.id, action="contact_deleted", resource_type="contact", resource_id=uuid.UUID(contact_id)))
    await session.commit()
    return {"status": "deleted"}