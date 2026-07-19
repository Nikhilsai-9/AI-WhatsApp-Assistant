"""API routes package — all routes are versioned under ``/api/v1``.

The single root router (``api_router``) is mounted in ``app.main`` with
the prefix ``/api``.  Every feature router below carries the additional
``/v1`` segment so URLs become ``/api/v1/<feature>/...``.
"""

from fastapi import APIRouter

from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.contacts import router as contacts_router
from app.api.dashboard import router as dashboard_router
from app.api.messages import router as messages_router
from app.api.settings import router as settings_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(ai_router, prefix="/v1/ai", tags=["ai"])
api_router.include_router(contacts_router, prefix="/v1/contacts", tags=["contacts"])
api_router.include_router(messages_router, prefix="/v1/messages", tags=["messages"])
api_router.include_router(dashboard_router, prefix="/v1/dashboard", tags=["dashboard"])
api_router.include_router(settings_router, prefix="/v1/settings", tags=["settings"])
api_router.include_router(webhooks_router, prefix="/v1/webhooks", tags=["webhooks"])
