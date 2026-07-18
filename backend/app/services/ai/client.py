"""
Multi-provider AI service.

Generates human-like WhatsApp replies that mimic the owner's communication
style. Supports Gemini, OpenAI, Anthropic, OpenRouter, MiniMax, and Ollama.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ─── Prompt templates ────────────────────────────────────────────

CONSENT_MESSAGE = """Hi 👋

I'm using an AI assistant that can help reply to my WhatsApp messages.

Would you like to continue chatting with the AI assistant?

Reply

YES

or

NO"""

SYSTEM_PROMPT_TELEGULISH = """You are a WhatsApp AI assistant that mimics the owner's communication style exactly.

RULES:
1. ALWAYS reply in Teluglish (Telugu words written in English letters, like how real Telugu friends chat on WhatsApp)
2. NEVER sound robotic or use formal language
3. Keep replies SHORT and NATURAL (1-3 sentences max)
4. Use common Telugu slang and expressions naturally
5. Mix Telugu and English words naturally (Teluglish style)
6. Use emojis sparingly and naturally, like a real person
7. Match the conversation tone (casual with friends, warm with family, professional with colleagues)
8. NEVER use Google Translate style - sound like a real Telugu friend chatting

EXAMPLES OF GOOD REPLIES:
- "haan, nenu vasta 10 mins lo"
- "em ayindi ra? cheppu"
- "ok fine, nenu chesta"
- "haan bro, malli plan cheyyam"
- "entha baga undhi ra, ela vellamo"
- "sare ra, naku teliyani"

EXAMPLES OF BAD REPLIES (NEVER DO THESE):
- "I am coming in 10 minutes" (too formal)
- "What happened?" (not Teluglish)
- "I will call you later" (not Teluglish)

CONTEXT FROM MEMORY:
{memory_context}

CONTACT RELATIONSHIP: {relationship_type}
CONTACT NAME: {contact_name}

CONVERSATION HISTORY (most recent last):
{conversation_history}

INCOMING MESSAGE: {incoming_message}

Generate a natural Teluglish reply that sounds exactly like the owner would respond:"""

SYSTEM_PROMPT_DEFAULT = """You are a WhatsApp AI assistant that mimics the owner's communication style exactly.

RULES:
1. Keep replies SHORT and NATURAL (1-3 sentences max)
2. NEVER sound robotic or use formal language
3. Use the owner's common expressions and emoji patterns
4. Match the conversation tone
5. Sound like a real person texting, not an AI

OWNER'S COMMUNICATION STYLE:
- Primary language: {language}
- Code-switching: {code_switching}
- Formality level: {formality}/10
- Emoji usage: {emoji_frequency} emojis per message
- Common phrases: {common_phrases}

CONTEXT FROM MEMORY:
{memory_context}

CONTACT RELATIONSHIP: {relationship_type}
CONTACT NAME: {contact_name}

CONVERSATION HISTORY (most recent last):
{conversation_history}

INCOMING MESSAGE: {incoming_message}

Generate a reply that sounds exactly like the owner would respond:"""


@dataclass
class ReplyContext:
    """Everything the AI needs to generate a contextual reply."""

    incoming_message: str
    conversation_history: list[dict] = field(default_factory=list)
    contact_name: str | None = None
    relationship_type: str = "friend"
    memory_context: str = ""
    personality_profile: dict | None = None
    language: str = "teluglish"
    reply_type: str = "auto"  # auto | quick | detailed | professional | funny | short | long


@dataclass
class GeneratedReply:
    text: str
    confidence: float
    provider: str
    model: str


class AIService:
    """Unified AI client with multi-provider support."""

    def __init__(self) -> None:
        self.provider = settings.ai_provider
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ─── Public API ─────────────────────────────────────────────

    async def generate_reply(self, ctx: ReplyContext) -> GeneratedReply:
        """Generate a WhatsApp reply for the given context."""
        logger.info("generating_reply", provider=self.provider, reply_type=ctx.reply_type)

        match self.provider:
            case "gemini":
                return await self._gemini_reply(ctx)
            case "openai":
                return await self._openai_reply(ctx)
            case "anthropic":
                return await self._anthropic_reply(ctx)
            case "openrouter":
                return await self._openrouter_reply(ctx)
            case "minimax":
                return await self._minimax_reply(ctx)
            case "ollama":
                return await self._ollama_reply(ctx)
            case _:
                raise ValueError(f"Unknown AI provider: {self.provider}")

    def get_consent_message(self) -> str:
        return CONSENT_MESSAGE

    # ─── Provider implementations ───────────────────────────────

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _gemini_reply(self, ctx: ReplyContext) -> GeneratedReply:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)

        prompt = self._build_prompt(ctx)
        response = await model.generate_content_async(prompt)
        text = response.text.strip()

        # Clean up any markdown formatting the model might add
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.85, provider="gemini", model=settings.gemini_model)

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _openai_reply(self, ctx: ReplyContext) -> GeneratedReply:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        prompt = self._build_prompt(ctx)

        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": "You are a WhatsApp AI assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=200,
        )
        text = response.choices[0].message.content.strip()
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.88, provider="openai", model=settings.openai_model)

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _anthropic_reply(self, ctx: ReplyContext) -> GeneratedReply:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        prompt = self._build_prompt(ctx)

        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=200,
            system="You are a WhatsApp AI assistant. Keep replies short and natural.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.90, provider="anthropic", model=settings.anthropic_model)

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _openrouter_reply(self, ctx: ReplyContext) -> GeneratedReply:
        client = await self._get_client()
        prompt = self._build_prompt(ctx)

        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.openrouter_model,
                "messages": [
                    {"role": "system", "content": "You are a WhatsApp AI assistant."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 200,
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.87, provider="openrouter", model=settings.openrouter_model)

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _minimax_reply(self, ctx: ReplyContext) -> GeneratedReply:
        client = await self._get_client()
        prompt = self._build_prompt(ctx)

        response = await client.post(
            "https://api.minimax.chat/v1/text/chatcompletion_v2",
            headers={"Authorization": f"Bearer {settings.minimax_api_key}"},
            json={
                "model": settings.minimax_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200,
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.82, provider="minimax", model=settings.minimax_model)

    @retry(wait=wait_exponential(min=2, max=10), stop=stop_after_attempt(3))
    async def _ollama_reply(self, ctx: ReplyContext) -> GeneratedReply:
        client = await self._get_client()
        prompt = self._build_prompt(ctx)

        response = await client.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        data = response.json()
        text = data["message"]["content"].strip()
        text = self._clean_reply(text)
        return GeneratedReply(text=text, confidence=0.80, provider="ollama", model=settings.ollama_model)

    # ─── Helpers ─────────────────────────────────────────────────

    def _build_prompt(self, ctx: ReplyContext) -> str:
        """Build the full prompt from context."""
        history = "\n".join(
            f"{'Owner' if m.get('direction') == 'outgoing' else (ctx.contact_name or 'Contact')}: {m.get('text', '')}"
            for m in ctx.conversation_history[-10:]
        )

        if ctx.personality_profile:
            return SYSTEM_PROMPT_DEFAULT.format(
                language=ctx.personality_profile.get("primary_language", "en"),
                code_switching=",".join(ctx.personality_profile.get("language_mixing", [])),
                formality=int(ctx.personality_profile.get("formality_score", 0.5) * 10),
                emoji_frequency=ctx.personality_profile.get("emoji_frequency", 0),
                common_phrases=",".join(ctx.personality_profile.get("common_phrases", [])[:5]),
                memory_context=ctx.memory_context or "No prior context.",
                relationship_type=ctx.relationship_type,
                contact_name=ctx.contact_name or "Friend",
                conversation_history=history or "No previous messages.",
                incoming_message=ctx.incoming_message,
            )
        else:
            return SYSTEM_PROMPT_TELEGULISH.format(
                memory_context=ctx.memory_context or "No prior context.",
                relationship_type=ctx.relationship_type,
                contact_name=ctx.contact_name or "Friend",
                conversation_history=history or "No previous messages.",
                incoming_message=ctx.incoming_message,
            )

    def _clean_reply(self, text: str) -> str:
        """Strip markdown and normalize the reply."""
        # Remove markdown code blocks
        text = re.sub(r"```[\w]*\n?", "", text)
        # Remove bold/italic markers
        text = re.sub(r"\*+", "", text)
        # Remove leading/trailing quotes
        text = text.strip('"\' ')
        # Collapse multiple spaces
        text = re.sub(r"  +", " ", text)
        # Remove any leftover "Reply:" or "Response:" prefixes
        text = re.sub(r"^(Reply|Response|Answer):\s*", "", text, flags=re.IGNORECASE)
        return text.strip()


# ─── Singleton ───────────────────────────────────────────────────
_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service