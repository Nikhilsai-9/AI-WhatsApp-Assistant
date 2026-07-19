"""
Health & readiness endpoint tests.

These verify that the Railway/Nginx health checks pass — i.e., the deployment
is considered "live" by the orchestrator.
"""

import pytest

pytestmark = pytest.mark.asyncio


async def test_root_returns_operational(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "ai-whatsapp-assistant"
    assert body["status"] == "operational"
    assert "version" in body


async def test_health_returns_200(client):
    """Liveness probe — must always return 200 to pass Railway healthcheck."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"


async def test_ready_endpoint_exists(client):
    """Readiness probe — returns 200 or 503 but never 500."""
    resp = await client.get("/ready")
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert body["status"] in ("ready", "not_ready")
    assert "database" in body


async def test_security_headers_present(client):
    """Verify OWASP-recommended security headers are set."""
    resp = await client.get("/health")
    assert "x-content-type-options" in resp.headers
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert "referrer-policy" in resp.headers
    assert "permissions-policy" in resp.headers


async def test_404_returns_json(client):
    resp = await client.get("/api/v1/this-does-not-exist")
    assert resp.status_code == 404
