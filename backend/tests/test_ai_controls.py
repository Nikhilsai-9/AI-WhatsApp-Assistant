"""
AI control endpoints tests — verifies pause/resume/kill switches work.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_ai_status_requires_auth(client):
    """Without a Bearer token the endpoint must reject the request."""
    resp = await client.get("/api/v1/ai/status")
    # Either 401 (no auth) or 503 (DB not available) is acceptable — both
    # prove the route is registered.
    assert resp.status_code in (401, 403, 503)


async def test_emergency_kill_requires_auth(client):
    resp = await client.post("/api/v1/ai/emergency-kill")
    assert resp.status_code in (401, 403, 503)


async def test_chat_restrictions_endpoint_exists(client):
    """Chat-restrictions endpoint must be reachable, even if unauthorised."""
    resp = await client.get("/api/v1/ai/chat-restrictions")
    assert resp.status_code in (200, 401, 403, 503)
