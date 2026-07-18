"""Webhook routes — WhatsApp bridge integration."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.message import MessageIngest
from app.services.whatsapp.pipeline import WhatsAppPipeline, get_pipeline

router = APIRouter()
logger = get_logger(__name__)


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    x_bridge_secret: str | None = Header(None, alias="X-Bridge-Secret"),
    session: AsyncSession = Depends(get_db),
):
    """
    Receives incoming WhatsApp messages from the bridge.

    The bridge authenticates via X-Bridge-Secret header.
    """
    if settings.bridge_webhook_secret and x_bridge_secret != settings.bridge_webhook_secret:
        raise HTTPException(status_code=401, detail="Invalid bridge secret")

    body = await request.json()
    try:
        payload = MessageIngest(**body)
    except Exception as exc:
        logger.error("invalid_webhook_payload", error=str(exc))
        raise HTTPException(status_code=422, detail="Invalid payload")

    pipeline = get_pipeline(session)
    reply_text = await pipeline.process_incoming(payload)

    return {"status": "ok", "reply": reply_text}


@router.post("/consent-callback")
async def consent_callback(
    request: Request,
    session: AsyncSession = Depends(get_db),
):
    """
    Receives consent responses (YES/NO) from contacts.

    The bridge forwards messages that match the consent message pattern.
    """
    body = await request.json()
    sender_jid = body.get("sender_jid", "")
    text = body.get("text", "").strip().upper()

    from sqlalchemy import select, update
    from app.models.contact import ConsentStatus, Contact
    from datetime import datetime, timezone

    result = await session.execute(
        select(Contact).where(Contact.whatsapp_jid == sender_jid)
    )
    contact = result.scalar_one_or_none()
    if not contact:
        return {"status": "ignored"}

    if text == "YES":
        contact.consent_status = ConsentStatus.APPROVED
        contact.consent_given_at = datetime.now(timezone.utc)
        logger.info("consent_approved_via_callback", contact=sender_jid)
    elif text == "NO":
        contact.consent_status = ConsentStatus.DENIED
        logger.info("consent_denied_via_callback", contact=sender_jid)
    else:
        return {"status": "ignored"}

    await session.commit()
    return {"status": "ok", "consent": contact.consent_status.value}