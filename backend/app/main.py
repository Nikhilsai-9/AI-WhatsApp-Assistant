"""
FastAPI application entry point — production-ready.

Startup sequence:
  1. Validate critical configuration
  2. Initialize database engine and (optionally) ensure schema
  3. Warm the embedder model in a thread (best-effort)
  4. Start background scheduled tasks
Shutdown sequence:
  1. Stop background tasks
  2. Close DB engine + Redis connections
  3. Emit a structured log line
"""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api import api_router
from app.core.config import settings
from app.core.logging import get_logger
from app.core.security_headers import SecurityHeadersMiddleware

logger = get_logger(__name__)


# ─── Startup helpers ────────────────────────────────────────────
async def _ensure_database() -> bool:
    """Test the database connection. Returns True if healthy."""
    from sqlalchemy import text

    try:
        from app.db.session import engine

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # pragma: no cover — network optional
        logger.error("database_unhealthy", error=str(exc))
        return False


async def _warm_embedder_async() -> None:
    """Run the embedder warmup off the event loop."""
    try:
        from app.services.memory.engine import warm_up_embedder

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, warm_up_embedder)
    except Exception as exc:
        logger.warning("embedder_warmup_failed", error=str(exc))


async def _start_scheduler() -> None:
    """Start the report / cleanup scheduler."""
    try:
        from app.services.scheduler import start_scheduler

        await start_scheduler()
    except Exception as exc:
        logger.warning("scheduler_start_failed", error=str(exc))


async def _stop_scheduler() -> None:
    try:
        from app.services.scheduler import stop_scheduler

        await stop_scheduler()
    except Exception as exc:  # pragma: no cover
        logger.warning("scheduler_stop_failed", error=str(exc))


async def _close_db() -> None:
    try:
        from app.db.session import engine

        await engine.dispose()
    except Exception as exc:  # pragma: no cover
        logger.warning("db_dispose_failed", error=str(exc))


# ─── Lifespan ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown hooks for the FastAPI app."""
    logger.info("app_starting", version=settings.version, env=settings.environment)

    db_ok = await _ensure_database()
    app.state.db_ready = db_ok
    if not db_ok:
        logger.warning(
            "app_starting_with_db_issue",
            hint="Set DATABASE_URL correctly. Some endpoints will return 503.",
        )

    # Embedder warmup + scheduler — both are best-effort.
    await asyncio.gather(
        _warm_embedder_async(),
        _start_scheduler(),
        return_exceptions=True,
    )

    try:
        yield
    finally:
        logger.info("app_shutting_down")
        await _stop_scheduler()
        await _close_db()


# ─── App instance ───────────────────────────────────────────────
app = FastAPI(
    title="AI WhatsApp Assistant API",
    description="Production AI assistant that auto-replies to WhatsApp messages.",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc" if settings.environment != "production" else None,
    openapi_url="/openapi.json" if settings.environment != "production" else None,
)

# ─── Middleware ─────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Security headers (HSTS, X-Frame-Options, etc.) — applied last so it
# affects every response including those modified by earlier middleware.
app.add_middleware(
    SecurityHeadersMiddleware,
    is_production=settings.environment == "production",
)

# ─── Routers ────────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


# ─── Health / readiness endpoints ───────────────────────────────
@app.get("/")
async def root() -> dict[str, Any]:
    return {"service": "ai-whatsapp-assistant", "version": settings.version, "status": "operational"}


@app.get("/health")
async def health() -> dict[str, Any]:
    """Liveness probe — returns 200 as long as the process is alive."""
    return {"status": "healthy", "version": settings.version}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Readiness probe — checks DB connectivity. Returns 503 if not ready."""
    db_ok = await _ensure_database()
    payload = {
        "status": "ready" if db_ok else "not_ready",
        "version": settings.version,
        "database": "up" if db_ok else "down",
    }
    code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=payload, status_code=code)


# ─── Exception handlers ────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__},
    )


# Convenience for `python -m app.main`
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=False,
        log_level="info",
    )
