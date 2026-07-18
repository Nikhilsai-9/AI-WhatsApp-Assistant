"""
WhatsApp message ingestion pipeline.

Handles the full flow from incoming bridge webhook → smart filter →
consent check → AI reply generation → bridge send.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.models.chat import Chat, ChatType
from app.models.contact import ConsentStatus, Contact
from app.models.message import Message, MessageDirection, MessageType
from app.models.settings import UserSettings
from app.schemas.message import MessageIngest
from app.services.ai.client import AIService, ReplyContext, get_ai_service
from app.services.memory.engine import MemoryEngine, get_memory_engine

logger = get_logger(__name__)

# ─── Smart filter patterns ──────────────────────────────────────
_OTP_PATTERN = re.compile(
    r"\b(otp|one.?time.?password|verification.?code|verify.?code|"
    r"login.?code|security.?code|transaction.?pin)\b",
    re.IGNORECASE,
)
_BANK_PATTERN = re.compile(
    r"\b(credited|debited|balance|account|bank|upi|neft|rtgs|"
    r"transaction|withdrawn|deposited|ifsc|banking)\b",
    re.IGNORECASE,
)
_SPAM_PATTERN = re.compile(
    r"\b(click here|free|winner|congratulations|lottery|"
    r"claim|urgent action|suspended account|verify now)\b",
    re.IGNORECASE,
)
_PROMO_PATTERN = re.compile(
    r"\b(offer|discount|deal|buy one|get one|limited time|"
    r"subscribe|unsubscribe|promo code|coupon)\b",
    re.IGNORECASE,
)


class WhatsAppPipeline:
    """
    Orchestrates the full message → reply pipeline.

    1. Validate & deduplicate (by whatsapp_message_id)
    2. Smart filter (OTP / bank / spam / promo)
    3. Consent check
    4. Media processing (OCR / transcription)
    5. Memory storage
    6. AI reply generation
    7. Send reply via bridge
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai: AIService = get_ai_service()
        self.memory: MemoryEngine = get_memory_engine(session)

    async def process_incoming(self, payload: MessageIngest) -> str | None:
        """
        Main entry point. Returns the generated reply text, or None if
        the message was filtered / consent denied.
        """
        logger.info(
            "processing_message",
            msg_id=payload.whatsapp_message_id,
            sender=payload.sender_jid,
        )

        # ── 1. Deduplicate ──────────────────────────────────────
        existing = await self.session.execute(
            select(Message).where(
                Message.whatsapp_message_id == payload.whatsapp_message_id
            )
        )
        if existing.scalar_one_or_none():
            logger.debug("duplicate_message", id=payload.whatsapp_message_id)
            return None

        # ── 2. Resolve / create contact ─────────────────────────
        contact = await self._get_or_create_contact(payload)
        if contact is None:
            return None

        # ── 3. Resolve / create chat ────────────────────────────
        chat = await self._get_or_create_chat(payload, contact)
        if chat is None:
            return None

        # ── 4. Smart filter ─────────────────────────────────────
        filter_reason = await self._smart_filter(payload, contact)
        if filter_reason:
            msg = await self._create_message(chat, payload, is_filtered=True, filter_reason=filter_reason)
            await self.session.commit()
            logger.info("message_filtered", reason=filter_reason)
            return None

        # ── 5. Consent check ────────────────────────────────────
        if contact.consent_status == ConsentStatus.PENDING:
            reply_text = self.ai.get_consent_message()
            await self._send_reply(chat.whatsapp_chat_id, reply_text)
            await self.session.commit()
            logger.info("consent_request_sent", contact=contact.whatsapp_jid)
            return reply_text

        if contact.consent_status in (ConsentStatus.DENIED, ConsentStatus.BLOCKED):
            logger.info("consent_denied", contact=contact.whatsapp_jid)
            return None

        # ── 6. Get user settings for mode checks ────────────────
        settings_result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == contact.user_id)
        )
        user_settings = settings_result.scalar_one_or_none()

        # ── 7. Check AI enabled ─────────────────────────────────
        if not user_settings or not user_settings.ai_enabled:
            logger.info("ai_disabled", contact=contact.whatsapp_jid)
            return None

        # ── 8. Check silent mode ────────────────────────────────
        if user_settings.silent_mode:
            if self._is_in_silent_hours(user_settings):
                logger.info("silent_mode_active", contact=contact.whatsapp_jid)
                return None

        # ── 9. Check office hours ───────────────────────────────
        if user_settings.office_hours_only:
            if not self._is_in_office_hours(user_settings):
                logger.info("outside_office_hours", contact=contact.whatsapp_jid)
                return None

        # ── 10. Check vacation mode ─────────────────────────────
        if user_settings.vacation_mode:
            reply_text = user_settings.vacation_message or "I'm currently on vacation and will reply when I'm back!"
            await self._send_reply(chat.whatsapp_chat_id, reply_text)
            await self.session.commit()
            logger.info("vacation_mode_reply_sent", contact=contact.whatsapp_jid)
            return reply_text

        # ── 11. Create message record ───────────────────────────
        msg = await self._create_message(chat, payload)
        await self.session.flush()

        # ── 12. Media processing ─────────────────────────────────
        await self._process_media(msg, payload)

        # ── 13. Store memory ─────────────────────────────────────
        try:
            await self.memory.store_from_message(msg)
        except Exception as exc:
            logger.warning("memory_store_failed", error=str(exc))

        # ── 14. Apply reply delay if configured ─────────────────
        if user_settings and user_settings.reply_delay_seconds > 0:
            import asyncio
            await asyncio.sleep(user_settings.reply_delay_seconds)

        # ── 15. Generate reply ───────────────────────────────────
        reply_text = await self._generate_reply(msg, contact, chat)
        if reply_text:
            await self._send_reply(chat.whatsapp_chat_id, reply_text)
            logger.info("reply_sent", contact=contact.whatsapp_jid, length=len(reply_text))

        await self.session.commit()
        return reply_text

    # ─── Internal helpers ───────────────────────────────────────

    async def _get_or_create_contact(self, payload: MessageIngest) -> Contact | None:
        """Find or create contact by WhatsApp JID."""
        stmt = select(Contact).where(Contact.whatsapp_jid == payload.sender_jid)
        result = await self.session.execute(stmt)
        contact = result.scalar_one_or_none()

        if contact is None:
            contact = Contact(
                whatsapp_jid=payload.sender_jid,
                display_name=payload.sender_name,
                consent_status=ConsentStatus.PENDING,
            )
            self.session.add(contact)
            await self.session.flush()
            logger.info("new_contact", jid=payload.sender_jid)

        else:
            # Update display name if we have a better one
            if payload.sender_name and not contact.display_name:
                contact.display_name = payload.sender_name
            contact.last_seen_at = datetime.now(timezone.utc)

        return contact

    async def _get_or_create_chat(self, payload: MessageIngest, contact: Contact) -> Chat | None:
        """Find or create chat. Returns None for group/broadcast/channel chats."""
        stmt = select(Chat).where(Chat.whatsapp_chat_id == payload.whatsapp_chat_id)
        result = await self.session.execute(stmt)
        chat = result.scalar_one_or_none()

        if chat is None:
            # Only process individual chats
            chat = Chat(
                contact_id=contact.id,
                whatsapp_chat_id=payload.whatsapp_chat_id,
                chat_type=ChatType.INDIVIDUAL,
                subject=contact.display_name,
            )
            self.session.add(chat)
            await self.session.flush()
            logger.info("new_chat", chat_id=payload.whatsapp_chat_id)

        return chat

    async def _smart_filter(self, payload: MessageIngest, contact: Contact) -> str | None:
        """Return filter reason string if message should be skipped."""
        text = payload.text_content or ""

        # Check user settings
        settings_result = await self.session.execute(
            select(UserSettings).where(UserSettings.user_id == contact.user_id)
        )
        user_settings = settings_result.scalar_one_or_none()

        if not text:
            return None  # Media-only messages pass through

        if user_settings and user_settings.filter_otps and _OTP_PATTERN.search(text):
            return "otp"
        if user_settings and user_settings.filter_bank_messages and _BANK_PATTERN.search(text):
            return "bank_message"
        if user_settings and user_settings.filter_spam and _SPAM_PATTERN.search(text):
            return "spam"
        if user_settings and user_settings.filter_promotions and _PROMO_PATTERN.search(text):
            return "promotion"

        return None

    async def _create_message(
        self,
        chat: Chat,
        payload: MessageIngest,
        is_filtered: bool = False,
        filter_reason: str | None = None,
    ) -> Message:
        msg = Message(
            chat_id=chat.id,
            whatsapp_message_id=payload.whatsapp_message_id,
            direction=payload.direction,
            message_type=payload.message_type,
            timestamp=payload.timestamp,
            text_content=payload.text_content,
            media_url=payload.media_url,
            media_mime_type=payload.media_mime_type,
            media_caption=payload.media_caption,
            sender_jid=payload.sender_jid,
            is_filtered=is_filtered,
            filter_reason=filter_reason,
        )
        self.session.add(msg)
        return msg

    async def _process_media(self, msg: Message, payload: MessageIngest) -> None:
        """Run OCR or transcription on media if available."""
        if not payload.media_url:
            return

        from app.services.media.processor import MediaProcessor

        processor = MediaProcessor(self.session)
        await processor.process(msg, payload.media_url, payload.media_mime_type)

    async def _generate_reply(
        self, msg: Message, contact: Contact, chat: Chat
    ) -> str | None:
        """Build context and call AI to generate a reply."""
        # Get conversation history
        history_result = await self.session.execute(
            select(Message)
            .where(Message.chat_id == chat.id)
            .order_by(Message.timestamp.desc())
            .limit(20)
            .options(selectinload(Message.chat))
        )
        history = list(reversed(history_result.scalars().all()))

        history_dicts = [
            {
                "direction": m.direction.value,
                "text": m.text_content or m.ocr_text or m.transcription or "[media]",
            }
            for m in history[:-1]  # exclude current message
        ]

        # Get memory context
        memory_context = await self.memory.get_context_for_contact(contact.id)

        # Get personality profile
        personality = None
        if contact.personality:
            personality = {
                "primary_language": contact.personality.primary_language,
                "language_mixing": contact.personality.language_mixing or [],
                "formality_score": contact.personality.formality_score,
                "emoji_frequency": contact.personality.emoji_frequency,
                "common_phrases": contact.personality.common_phrases or [],
            }

        ctx = ReplyContext(
            incoming_message=msg.text_content or msg.ocr_text or msg.transcription or "[media message]",
            conversation_history=history_dicts,
            contact_name=contact.display_name,
            relationship_type=contact.relationship_type or "friend",
            memory_context=memory_context,
            personality_profile=personality,
            language="teluglish",
        )

        try:
            reply = await self.ai.generate_reply(ctx)
            # Store the AI reply as an outgoing message
            ai_msg = Message(
                chat_id=chat.id,
                whatsapp_message_id=f"ai-{uuid.uuid4().hex[:20]}",
                direction=MessageDirection.OUTGOING,
                message_type=MessageType.TEXT,
                timestamp=datetime.now(timezone.utc),
                text_content=reply.text,
                is_ai_reply=True,
                ai_confidence=reply.confidence,
            )
            self.session.add(ai_msg)
            return reply.text
        except Exception as exc:
            logger.error("reply_generation_failed", error=str(exc))
            return None

    async def _send_reply(self, chat_id: str, text: str) -> None:
        """POST reply to the WhatsApp bridge for sending."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await client.post(
                    f"{settings.bridge_url}/send",
                    json={"chat_id": chat_id, "text": text},
                    headers={"X-Bridge-Secret": settings.bridge_webhook_secret},
                )
        except Exception as exc:
            logger.error("bridge_send_failed", error=str(exc))
            # Queue for retry
            from app.services.queue.retry import get_retry_queue
            queue = get_retry_queue()
            await queue.enqueue(chat_id=chat_id, text=text)

    def _is_in_silent_hours(self, settings_obj: UserSettings) -> bool:
        """Check if current time is within silent hours."""
        if not settings_obj.silent_start or not settings_obj.silent_end:
            return False
        try:
            now = datetime.now(timezone.utc).astimezone()
            start_h, start_m = map(int, settings_obj.silent_start.split(":"))
            end_h, end_m = map(int, settings_obj.silent_end.split(":"))
            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            if start_minutes <= end_minutes:
                return start_minutes <= current_minutes < end_minutes
            else:
                return current_minutes >= start_minutes or current_minutes < end_minutes
        except (ValueError, AttributeError):
            return False

    def _is_in_office_hours(self, settings_obj: UserSettings) -> bool:
        """Check if current time is within office hours."""
        if not settings_obj.office_start or not settings_obj.office_end:
            return False
        try:
            now = datetime.now(timezone.utc).astimezone()
            start_h, start_m = map(int, settings_obj.office_start.split(":"))
            end_h, end_m = map(int, settings_obj.office_end.split(":"))
            current_minutes = now.hour * 60 + now.minute
            start_minutes = start_h * 60 + start_m
            end_minutes = end_h * 60 + end_m
            return start_minutes <= current_minutes < end_minutes
        except (ValueError, AttributeError):
            return False


def get_pipeline(session: AsyncSession) -> WhatsAppPipeline:
    return WhatsAppPipeline(session)
