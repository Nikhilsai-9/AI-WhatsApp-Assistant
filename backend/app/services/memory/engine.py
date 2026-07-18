"""
Memory engine — vector-backed semantic search + importance scoring.

Uses sentence-transformers for embeddings and pgvector for similarity search.
Handles memory creation, retrieval, importance scoring, and compression.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.memory import Memory, MemoryType
from app.models.message import Message

logger = get_logger(__name__)

# ─── Embedding model (lazy-loaded + warmup) ─────────────────────
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        _embedder = SentenceTransformer(settings.embedding_model)
        _embedder.max_seq_length = 256  # Optimize for memory
    return _embedder


def _embed(text: str) -> list[float]:
    """Generate embedding vector for *text*."""
    model = _get_embedder()
    return model.encode(text, normalize_embeddings=True).tolist()


def warm_up_embedder():
    """Pre-load the embedding model at startup to avoid first-request latency."""
    embedder = _get_embedder()
    # Run a dummy encode to warm up the model
    embedder.encode(["warmup"], show_progress_bar=False)
    logger.info("embedder_warmed_up", model=settings.embedding_model)


class MemoryEngine:
    """Manages long-term and short-term memory with vector search."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ─── Store ──────────────────────────────────────────────────

    async def store(
        self,
        content: str,
        contact_id: uuid.UUID | None = None,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        source_message_id: uuid.UUID | None = None,
        metadata: dict | None = None,
        importance: float = 5.0,
    ) -> Memory:
        """Create a new memory with vector embedding."""
        embedding = _embed(content)

        memory = Memory(
            contact_id=contact_id,
            embedding=embedding,
            content=content,
            memory_type=memory_type,
            source_message_id=source_message_id,
            metadata_json=metadata or {},
            importance_score=importance,
        )
        self.session.add(memory)
        await self.session.flush()
        logger.debug("memory_stored", memory_id=str(memory.id), type=memory_type.value)
        return memory

    async def store_from_message(self, message: Message) -> Memory | None:
        """Extract and store memory from a message."""
        text = message.text_content or message.ocr_text or message.transcription
        if not text or len(text.strip()) < 5:
            return None

        # Determine memory type based on content
        memory_type = self._classify_memory_type(text)

        # Score importance
        importance = self._score_importance(text)

        return await self.store(
            content=text,
            contact_id=message.chat.contact_id if message.chat else None,
            memory_type=memory_type,
            source_message_id=message.id,
            metadata={"message_type": message.message_type.value},
            importance=importance,
        )

    # ─── Retrieve ───────────────────────────────────────────────

    async def search(
        self,
        query: str,
        contact_id: uuid.UUID | None = None,
        memory_type: MemoryType | None = None,
        limit: int = 5,
    ) -> list[Memory]:
        """
        Semantic similarity search using pgvector.

        Returns memories most relevant to *query*, optionally filtered
        by contact and/or memory type.
        """
        query_embedding = _embed(query)

        stmt = (
            select(Memory)
            .order_by(Memory.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )

        if contact_id:
            stmt = stmt.where(Memory.contact_id == contact_id)
        if memory_type:
            stmt = stmt.where(Memory.memory_type == memory_type)

        result = await self.session.execute(stmt)
        memories = list(result.scalars().all())

        # Update access stats
        for m in memories:
            m.access_count += 1
            m.last_accessed_at = datetime.now(timezone.utc)

        await self.session.flush()
        return memories

    async def get_context_for_contact(
        self, contact_id: uuid.UUID, limit: int = 10
    ) -> str:
        """Build a human-readable context string for AI prompts."""
        memories = await self.search(
            query="", contact_id=contact_id, limit=limit
        )
        if not memories:
            return ""

        lines = ["Relevant context from previous conversations:"]
        for m in memories:
            lines.append(f"- {m.content}")
        return "\n".join(lines)

    # ─── Maintenance ────────────────────────────────────────────

    async def compress(self, max_items: int = 5000) -> int:
        """
        Memory compression: keep high-importance memories, evict
        low-importance ones when the cap is exceeded.
        """
        count_result = await self.session.execute(
            select(func.count(Memory.id))
        )
        total = count_result.scalar() or 0

        if total <= max_items:
            return 0

        to_delete = total - max_items

        # Delete lowest-importance, least-accessed memories
        stmt = (
            Memory.__table__.delete()
            .where(
                Memory.id.in_(
                    select(Memory.id)
                    .order_by(
                        Memory.importance_score.asc(),
                        Memory.access_count.asc(),
                        Memory.created_at.asc(),
                    )
                    .limit(to_delete)
                )
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        logger.info("memory_compressed", deleted=to_delete)
        return to_delete

    async def delete_contact_memories(self, contact_id: uuid.UUID) -> int:
        """Delete all memories for a contact (GDPR / owner request)."""
        stmt = Memory.__table__.delete().where(Memory.contact_id == contact_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount

    async def count(self, contact_id: uuid.UUID | None = None) -> int:
        """Count total memories, optionally filtered by contact."""
        stmt = select(func.count(Memory.id))
        if contact_id:
            stmt = stmt.where(Memory.contact_id == contact_id)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    # ─── Helpers ────────────────────────────────────────────────

    def _classify_memory_type(self, text: str) -> MemoryType:
        """Classify memory type based on content keywords."""
        text_lower = text.lower()
        if any(k in text_lower for k in ["remember", "don't forget", "promise", "birthday", "anniversary"]):
            return MemoryType.SEMANTIC
        if any(k in text_lower for k in ["yesterday", "today", "meeting", "plan", "schedule"]):
            return MemoryType.EPISODIC
        return MemoryType.LONG_TERM

    def _score_importance(self, text: str) -> float:
        """Score 0-10 based on content signals."""
        score = 5.0
        text_lower = text.lower()

        # Boosters
        if any(k in text_lower for k in ["birthday", "anniversary", "important", "urgent", "meeting"]):
            score += 2.0
        if any(k in text_lower for k in ["promise", "swear", "commit", "must", "critical"]):
            score += 1.5
        if len(text) > 100:
            score += 0.5

        # Reducers
        if any(k in text_lower for k in ["lol", "haha", "joke", "btw", "typo"]):
            score -= 1.0
        if len(text) < 20:
            score -= 0.5

        return max(0.0, min(10.0, score))


# ─── Singleton ───────────────────────────────────────────────────
_memory_engine: MemoryEngine | None = None


def get_memory_engine(session: AsyncSession) -> MemoryEngine:
    return MemoryEngine(session)