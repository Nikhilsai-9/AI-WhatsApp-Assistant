"""
Background scheduler for periodic tasks (daily reports, cleanup, etc.).

We use ``apscheduler`` when available. If it isn't installed (e.g. a
minimal container build) we fall back to a hand-rolled asyncio loop so
that the application can still start and serve requests.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, Awaitable, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


# ─── Task registry ────────────────────────────────────────────────
_tasks: list[Callable[[], Awaitable[None]]] = []
_scheduler: Any | None = None
_runner_task: asyncio.Task[None] | None = None
_runner_stop: asyncio.Event | None = None


def register_task(coro: Callable[[], Awaitable[None]]) -> None:
    """Register a coroutine to run once per scheduler tick."""
    _tasks.append(coro)


async def _run_apscheduler() -> None:
    """Run the loop using APScheduler if available."""
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
    except Exception:  # pragma: no cover
        return await _run_simple_loop()

    global _scheduler
    scheduler = AsyncIOScheduler(timezone="UTC")
    for coro in _tasks:
        try:
            scheduler.add_job(coro, "interval", minutes=60, id=coro.__name__, replace_existing=True)
        except Exception as exc:  # pragma: no cover
            logger.warning("scheduler_add_job_failed", job=coro.__name__, error=str(exc))
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler_started", mode="apscheduler", jobs=len(_tasks))


async def _run_simple_loop() -> None:
    """Lightweight asyncio loop used when APScheduler is unavailable."""
    global _runner_stop
    _runner_stop = asyncio.Event()
    assert _runner_stop is not None

    async def _loop() -> None:
        interval = 3600  # 1 hour
        while _runner_stop and not _runner_stop.is_set():
            await asyncio.sleep(interval)
            for coro in _tasks:
                try:
                    await coro()
                except Exception as exc:  # pragma: no cover
                    logger.warning("scheduler_task_failed", task=coro.__name__, error=str(exc))

    global _runner_task
    _runner_task = asyncio.create_task(_loop(), name="aiwa-scheduler")
    logger.info("scheduler_started", mode="asyncio-loop", jobs=len(_tasks))


async def start_scheduler() -> None:
    """Boot the scheduler. Safe to call multiple times — it's a no-op afterwards."""
    if _scheduler is not None or _runner_task is not None:
        return
    await _run_apscheduler()


async def stop_scheduler() -> None:
    """Stop the scheduler and cancel any pending loops."""
    global _scheduler, _runner_task, _runner_stop
    if _scheduler is not None:
        with contextlib.suppress(Exception):
            _scheduler.shutdown(wait=False)
        _scheduler = None
    if _runner_stop is not None:
        _runner_stop.set()
    if _runner_task is not None:
        _runner_task.cancel()
        with contextlib.suppress(BaseException):
            await _runner_task
    _runner_task = None
    _runner_stop = None


# ─── Default tasks ────────────────────────────────────────────────
async def _noop_daily_report() -> None:
    """Placeholder for the daily AI report job.

    Implemented as a no-op so the scheduler always has at least one task
    and can be exercised in CI / unit tests.
    """
    logger.debug("daily_report_tick", note="task implementation pending")
    return None


# Register default tasks on import so the scheduler always has work.
register_task(_noop_daily_report)
