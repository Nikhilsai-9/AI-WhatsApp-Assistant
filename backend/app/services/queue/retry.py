"""
Redis-based retry queue for failed message sends.

Ensures no messages are lost when the bridge is temporarily unavailable.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RetryQueue:
    """
    Redis-backed retry queue with exponential backoff.

    Failed messages are queued and retried with increasing delays.
    """

    QUEUE_KEY = "aiwa:retry_queue"
    MAX_RETRIES = 5
    BASE_DELAY = 5  # seconds
    MAX_DELAY = 300  # 5 minutes

    def __init__(self) -> None:
        self._redis = None
        self._processing = False

    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            import redis.asyncio as redis
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def enqueue(
        self,
        chat_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
        retry_count: int = 0,
    ) -> None:
        """Add a failed message to the retry queue."""
        redis = await self._get_redis()
        
        entry = {
            "chat_id": chat_id,
            "text": text,
            "metadata": metadata or {},
            "retry_count": retry_count,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
            "next_retry_at": datetime.now(timezone.utc).timestamp() + self._calculate_delay(retry_count),
        }
        
        await redis.rpush(self.QUEUE_KEY, json.dumps(entry))
        logger.info("retry_queued", chat_id=chat_id, retry_count=retry_count)

    async def dequeue(self) -> dict[str, Any] | None:
        """Get the next message ready for retry."""
        redis = await self._get_redis()
        
        # Get queue length
        length = await redis.llen(self.QUEUE_KEY)
        if length == 0:
            return None
        
        # Peek at all entries and find one ready to retry
        entries = await redis.lrange(self.QUEUE_KEY, 0, -1)
        now = datetime.now(timezone.utc).timestamp()
        
        for i, entry_str in enumerate(entries):
            entry = json.loads(entry_str)
            if entry["next_retry_at"] <= now:
                # Remove from queue
                await redis.lrem(self.QUEUE_KEY, 1, entry_str)
                return entry
        
        return None

    async def process_queue(self, send_func) -> int:
        """
        Process all ready messages in the queue.
        Returns the number of messages processed.
        """
        if self._processing:
            return 0
        
        self._processing = True
        processed = 0
        
        try:
            redis = await self._get_redis()
            
            while True:
                entry = await self.dequeue()
                if entry is None:
                    break
                
                try:
                    await send_func(entry["chat_id"], entry["text"])
                    logger.info("retry_success", chat_id=entry["chat_id"])
                    processed += 1
                except Exception as exc:
                    retry_count = entry["retry_count"] + 1
                    if retry_count < self.MAX_RETRIES:
                        # Re-queue with incremented retry count
                        await self.enqueue(
                            chat_id=entry["chat_id"],
                            text=entry["text"],
                            metadata=entry.get("metadata"),
                            retry_count=retry_count,
                        )
                        logger.warning("retry_rescheduled", chat_id=entry["chat_id"], retry_count=retry_count)
                    else:
                        # Max retries exceeded, log and discard
                        logger.error("retry_exhausted", chat_id=entry["chat_id"])
                
                # Small delay to prevent overwhelming the bridge
                await asyncio.sleep(0.5)
        finally:
            self._processing = False
        
        return processed

    async def get_queue_size(self) -> int:
        """Get the number of messages in the retry queue."""
        redis = await self._get_redis()
        return await redis.llen(self.QUEUE_KEY)

    async def clear(self) -> None:
        """Clear all messages from the retry queue."""
        redis = await self._get_redis()
        await redis.delete(self.QUEUE_KEY)
        logger.info("retry_queue_cleared")

    def _calculate_delay(self, retry_count: int) -> int:
        """Calculate exponential backoff delay."""
        delay = self.BASE_DELAY * (2 ** retry_count)
        return min(delay, self.MAX_DELAY)

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()


# Global instance
_retry_queue: RetryQueue | None = None


def get_retry_queue() -> RetryQueue:
    """Get or create the retry queue instance."""
    global _retry_queue
    if _retry_queue is None:
        _retry_queue = RetryQueue()
    return _retry_queue


async def start_retry_worker(send_func, interval: int = 30) -> None:
    """
    Start a background worker that processes the retry queue.
    
    Args:
        send_func: Async function(chat_id, text) to send messages
        interval: Seconds between processing cycles
    """
    queue = get_retry_queue()
    
    while True:
        try:
            processed = await queue.process_queue(send_func)
            if processed > 0:
                logger.info("retry_batch_processed", count=processed)
        except Exception as exc:
            logger.error("retry_worker_error", error=str(exc))
        
        await asyncio.sleep(interval)