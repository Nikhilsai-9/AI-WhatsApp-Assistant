"""API routes package."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.contacts import router as contacts_router
from app.api.messages import router as messages_router
from app.api.dashboard import router as dashboard_router
from app.api.settings import router as settings_router
from app.api.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(contacts_router, prefix="/contacts", tags=["contacts"])
api_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(settings_router, prefix="/settings", tags=["settings"])
api_router.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])