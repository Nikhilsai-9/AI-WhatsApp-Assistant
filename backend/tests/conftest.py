"""
Pytest fixtures — shared across all backend tests.

Strategy:
- Use SQLite in-memory for fast, isolated unit tests.
- Mock external services (Redis, AI providers, WhatsApp bridge).
- Provide a FastAPI TestClient wired up to the in-memory app.
"""

from __future__ import annotations

import os

# Force test-friendly env vars BEFORE the app imports settings.
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-32-chars-long-1234")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SYNC_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')

from typing import AsyncGenerator

import pytest
import pytest_asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop so async fixtures can share state."""
    import asyncio

    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def app_instance():
    """Lazy import the FastAPI app so env vars above take effect first."""
    from app.main import app

    return app


@pytest_asyncio.fixture
async def client(app_instance) -> AsyncGenerator:
    """Async HTTPX client bound to the FastAPI app."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app_instance)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
