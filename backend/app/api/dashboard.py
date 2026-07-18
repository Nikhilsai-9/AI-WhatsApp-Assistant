"""Dashboard stats route."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.chat import Chat
from app.models.contact import ConsentStatus, Contact
from app.models.memory import Memory
from app.models.message import Message
from app.models.user import User
from app.schemas.dashboard import ActivitySummary, ContactSummary, DashboardStats

router = APIRouter()


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)

    # Contact counts
    total_result = await session.execute(
        select(func.count(Contact.id)).where(Contact.user_id == user.id)
    )
    total_contacts = total_result.scalar() or 0

    approved_result = await session.execute(
        select(func.count(Contact.id))
        .where(Contact.user_id == user.id)
        .where(Contact.consent_status == ConsentStatus.APPROVED)
    )
    approved_contacts = approved_result.scalar() or 0

    pending_result = await session.execute(
        select(func.count(Contact.id))
        .where(Contact.user_id == user.id)
        .where(Contact.consent_status == ConsentStatus.PENDING)
    )
    pending_contacts = pending_result.scalar() or 0

    blocked_result = await session.execute(
        select(func.count(Contact.id))
        .where(Contact.user_id == user.id)
        .where(Contact.is_blacklisted == True)  # noqa: E712
    )
    blocked_contacts = blocked_result.scalar() or 0

    # Message counts
    today_result = await session.execute(
        select(func.count(Message.id))
        .join(Message.chat)
        .join(Chat.contact)
        .where(Contact.user_id == user.id)
        .where(Message.timestamp >= today_start)
    )
    messages_today = today_result.scalar() or 0

    week_result = await session.execute(
        select(func.count(Message.id))
        .join(Message.chat)
        .join(Chat.contact)
        .where(Contact.user_id == user.id)
        .where(Message.timestamp >= week_start)
    )
    messages_this_week = week_result.scalar() or 0

    ai_replies_result = await session.execute(
        select(func.count(Message.id))
        .join(Message.chat)
        .join(Chat.contact)
        .where(Contact.user_id == user.id)
        .where(Message.is_ai_reply == True)  # noqa: E712
        .where(Message.timestamp >= today_start)
    )
    ai_replies_today = ai_replies_result.scalar() or 0

    # Memory count
    memory_result = await session.execute(select(func.count(Memory.id)))
    memory_items = memory_result.scalar() or 0

    # Learning progress: based on approved contacts with personality profiles
    learning_progress = min(100.0, (approved_contacts / 10.0) * 100.0)

    return DashboardStats(
        total_contacts=total_contacts,
        approved_contacts=approved_contacts,
        pending_contacts=pending_contacts,
        blocked_contacts=blocked_contacts,
        messages_today=messages_today,
        messages_this_week=messages_this_week,
        ai_replies_today=ai_replies_today,
        memory_items=memory_items,
        learning_progress=learning_progress,
    )


@router.get("/activity", response_model=list[ActivitySummary])
async def get_activity(
    days: int = 7,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    results = []
    for i in range(days):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        incoming = await session.scalar(
            select(func.count(Message.id))
            .join(Message.chat)
            .join(Chat.contact)
            .where(Contact.user_id == user.id)
            .where(Message.direction == "incoming")
            .where(Message.timestamp >= day_start, Message.timestamp < day_end)
        )
        outgoing = await session.scalar(
            select(func.count(Message.id))
            .join(Message.chat)
            .join(Chat.contact)
            .where(Contact.user_id == user.id)
            .where(Message.direction == "outgoing")
            .where(Message.timestamp >= day_start, Message.timestamp < day_end)
        )
        ai_replies = await session.scalar(
            select(func.count(Message.id))
            .join(Message.chat)
            .join(Chat.contact)
            .where(Contact.user_id == user.id)
            .where(Message.is_ai_reply == True)  # noqa: E712
            .where(Message.timestamp >= day_start, Message.timestamp < day_end)
        )

        results.append(
            ActivitySummary(
                date=day_start.strftime("%Y-%m-%d"),
                incoming=incoming or 0,
                outgoing=outgoing or 0,
                ai_replies=ai_replies or 0,
            )
        )
    return list(reversed(results))


@router.get("/top-contacts", response_model=list[ContactSummary])
async def get_top_contacts(
    limit: int = 10,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from app.models.chat import Chat
    
    # Single query with subqueries to avoid N+1
    msg_count_subq = (
        select(Message.chat_id, func.count(Message.id).label("msg_count"))
        .group_by(Message.chat_id)
        .subquery()
    )
    
    last_msg_subq = (
        select(
            Message.chat_id,
            func.max(Message.timestamp).label("last_msg_at")
        )
        .group_by(Message.chat_id)
        .subquery()
    )
    
    chat_contact_subq = (
        select(Chat.id, Chat.contact_id)
        .subquery()
    )
    
    result = await session.execute(
        select(
            Contact,
            func.coalesce(msg_count_subq.c.msg_count, 0).label("message_count"),
            last_msg_subq.c.last_msg_at.label("last_message_at")
        )
        .outerjoin(chat_contact_subq, Contact.id == chat_contact_subq.c.contact_id)
        .outerjoin(msg_count_subq, chat_contact_subq.c.id == msg_count_subq.c.chat_id)
        .outerjoin(last_msg_subq, chat_contact_subq.c.id == last_msg_subq.c.chat_id)
        .where(Contact.user_id == user.id)
        .where(Contact.consent_status == ConsentStatus.APPROVED)
        .order_by(Contact.last_seen_at.desc())
        .limit(limit)
    )
    
    rows = result.all()
    return [
        ContactSummary(
            id=str(row[0].id),
            display_name=row[0].display_name,
            whatsapp_jid=row[0].whatsapp_jid,
            message_count=row[1] or 0,
            last_message_at=row[2],
            consent_status=row[0].consent_status.value,
            is_favorite=row[0].is_favorite,
        )
        for row in rows
    ]
