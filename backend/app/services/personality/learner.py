"""
Personality learner — analyzes owner's sent messages to build per-contact
communication style profiles.

Extracts: vocabulary, emoji usage, sentence length, greeting/ending patterns,
language mixing, formality, warmth, humor, and relationship type.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.models.message import Message, MessageDirection
from app.models.personality import PersonalityProfile

logger = get_logger(__name__)

# ─── Emoji regex ────────────────────────────────────────────────
_EMOJI_RE = re.compile(
    "[\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F1E0-\U0001F1FF"
    "\U00002702-\U000027B0"
    "\U000024C2-\U0001F251]+"
)

# ─── Common Telugu / Hinglish words ─────────────────────────────
_TELUGU_WORDS = {
    "nenu", "naaku", "naa", "vunda", "vasta", "undhi", "ayindi", "cheyy",
    "ra", "le", "ka", "ante", "kani", "ippudu", "tappa", "sare", "haan",
    "bro", "entha", "baga", "ela", "vellamo", "malli", "cheppu", "teliyani",
    "ok", "fine", "vastunnava", "ra", "da", "em", "kya", "haan", "nahi",
    "bhai", "yaar", "kya", "sab", "theek", "chalo", "dekho", "bol",
}
_HINDI_WORDS = {
    "kya", "haan", "nahi", "bhai", "yaar", "sab", "theek", "chalo",
    "dekho", "bol", "kaise", "kyun", "tab", "ab", "phir", "lekin",
    "aur", "bhi", "to", "hi", "matlab", "shayad", "pakka", "zaroor",
}


class PersonalityLearner:
    """Learns and updates personality profiles from message history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def learn_from_messages(self, contact_id: uuid.UUID) -> PersonalityProfile:
        """
        Analyze all outgoing messages to this contact and update their
        personality profile.
        """
        # Fetch outgoing messages
        stmt = (
            select(Message)
            .join(Message.chat)
            .where(Message.chat.has(contact_id=contact_id))
            .where(Message.direction == MessageDirection.OUTGOING)
            .where(Message.text_content.isnot(None))
            .order_by(Message.timestamp.desc())
            .limit(500)
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())

        if not messages:
            return await self._get_or_create_profile(contact_id)

        texts = [m.text_content for m in messages if m.text_content]

        # Get or create profile
        profile = await self._get_or_create_profile(contact_id)

        # Update metrics
        profile.message_count = len(texts)
        profile.avg_sentence_length = self._avg_sentence_length(texts)
        profile.emoji_frequency = self._emoji_frequency(texts)
        profile.common_emojis = self._top_emojis(texts, top_n=10)
        profile.caps_usage = self._caps_usage(texts)
        profile.exclamation_usage = self._exclamation_usage(texts)
        profile.greeting_patterns = self._extract_greetings(texts)
        profile.ending_patterns = self._extract_endings(texts)
        profile.common_words = self._top_words(texts, top_n=100)
        profile.common_phrases = self._top_phrases(texts, top_n=20)
        profile.slang = self._extract_slang(texts)
        profile.language_mixing = self._detect_language_mixing(texts)
        profile.code_switching_pattern = self._detect_code_switching(texts)
        profile.formality_score = self._score_formality(texts)
        profile.warmth_score = self._score_warmth(texts)
        profile.humor_score = self._score_humor(texts)
        profile.confidence = min(1.0, len(texts) / 100.0)  # 0-1, full at 100 msgs

        await self.session.flush()
        logger.info("personality_updated", contact_id=str(contact_id), msgs=len(texts))
        return profile

    # ─── Analysis helpers ───────────────────────────────────────

    def _avg_sentence_length(self, texts: list[str]) -> float:
        if not texts:
            return 12.0
        all_words = sum(len(t.split()) for t in texts)
        return all_words / len(texts)

    def _emoji_frequency(self, texts: list[str]) -> float:
        if not texts:
            return 0.0
        total_emoji = sum(len(_EMOJI_RE.findall(t)) for t in texts)
        return total_emoji / len(texts)

    def _top_emojis(self, texts: list[str], top_n: int = 10) -> list[str]:
        all_emojis = _EMOJI_RE.findall(" ".join(texts))
        return [e for e, _ in Counter(all_emojis).most_common(top_n)]

    def _caps_usage(self, texts: list[str]) -> float:
        if not texts:
            return 0.0
        return sum(1 for t in texts if any(c.isupper() for c in t)) / len(texts)

    def _exclamation_usage(self, texts: list[str]) -> float:
        if not texts:
            return 0.0
        return sum(1 for t in texts if "!" in t) / len(texts)

    def _extract_greetings(self, texts: list[str]) -> list[str]:
        greetings = []
        for t in texts[:50]:  # first 50 messages
            first_word = t.strip().split()[0].lower() if t.strip() else ""
            if first_word in {"hi", "hey", "hello", "hai", "haan", "yo", "sup"}:
                greetings.append(first_word)
        return list(dict.fromkeys(greetings))[:5]

    def _extract_endings(self, texts: list[str]) -> list[str]:
        endings = []
        for t in texts[:50]:
            words = t.strip().split()
            if words:
                last_word = words[-1].lower().rstrip("!.,")
                endings.append(last_word)
        return list(dict.fromkeys(endings))[:5]

    def _top_words(self, texts: list[str], top_n: int = 100) -> list[str]:
        words = []
        for t in texts:
            words.extend(re.findall(r"\b[a-zA-Z']{2,}\b", t.lower()))
        return [w for w, _ in Counter(words).most_common(top_n)]

    def _top_phrases(self, texts: list[str], top_n: int = 20) -> list[str]:
        """Extract 2-word phrases."""
        phrases = []
        for t in texts:
            words = re.findall(r"\b[a-zA-Z']{2,}\b", t.lower())
            phrases.extend(" ".join(words[i : i + 2]) for i in range(len(words) - 1))
        return [p for p, _ in Counter(phrases).most_common(top_n)]

    def _extract_slang(self, texts: list[str]) -> list[str]:
        all_words = set()
        for t in texts:
            all_words.update(re.findall(r"\b[a-zA-Z']{2,}\b", t.lower()))
        return list(all_words & _TELUGU_WORDS | all_words & _HINDI_WORDS)[:20]

    def _detect_language_mixing(self, texts: list[str]) -> list[str]:
        all_words = set()
        for t in texts:
            all_words.update(re.findall(r"\b[a-zA-Z']{2,}\b", t.lower()))

        languages = []
        if all_words & _TELUGU_WORDS:
            languages.append("telugu")
        if all_words & _HINDI_WORDS:
            languages.append("hindi")
        if languages:
            languages.append("english")
        return list(dict.fromkeys(languages))

    def _detect_code_switching(self, texts: list[str]) -> str | None:
        all_words = set()
        for t in texts:
            all_words.update(re.findall(r"\b[a-zA-Z']{2,}\b", t.lower()))

        telugu_count = len(all_words & _TELUGU_WORDS)
        hindi_count = len(all_words & _HINDI_WORDS)

        if telugu_count > 2:
            return "teluglish"
        if hindi_count > 2:
            return "hinglish"
        return None

    def _score_formality(self, texts: list[str]) -> float:
        """Score 0-1: 0=very casual, 1=very formal."""
        if not texts:
            return 0.5
        score = 0.5
        for t in texts:
            t_lower = t.lower()
            if any(w in t_lower for w in ["please", "thank", "regards", "sincerely"]):
                score += 0.1
            if any(w in t_lower for w in ["lol", "haha", "bro", "yaar", "ra"]):
                score -= 0.05
            if t.isupper():
                score += 0.05
        return max(0.0, min(1.0, score))

    def _score_warmth(self, texts: list[str]) -> float:
        """Score 0-1: warmth based on affectionate language."""
        if not texts:
            return 0.5
        score = 0.5
        for t in texts:
            t_lower = t.lower()
            if any(w in t_lower for w in ["love", "miss", "dear", "sweet", "❤️", "🥰"]):
                score += 0.1
            if any(w in t_lower for w in ["ok", "fine", "k", "hmm"]):
                score -= 0.02
        return max(0.0, min(1.0, score))

    def _score_humor(self, texts: list[str]) -> float:
        """Score 0-1: humor based on laughing expressions."""
        if not texts:
            return 0.5
        score = 0.5
        for t in texts:
            if any(w in t for w in ["lol", "lmao", "haha", "😂", "🤣"]):
                score += 0.1
        return max(0.0, min(1.0, score))

    async def _get_or_create_profile(self, contact_id: uuid.UUID) -> PersonalityProfile:
        stmt = select(PersonalityProfile).where(
            PersonalityProfile.contact_id == contact_id
        )
        result = await self.session.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = PersonalityProfile(contact_id=contact_id)
            self.session.add(profile)
            await self.session.flush()
        return profile