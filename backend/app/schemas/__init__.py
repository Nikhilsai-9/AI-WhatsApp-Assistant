"""Schemas package: all Pydantic request/response models."""

from app.schemas.auth import (
    TokenPayload,
    LoginRequest,
    RegisterRequest,
    AuthResponse,
    RefreshRequest,
)
from app.schemas.contact import (
    ContactCreate,
    ContactUpdate,
    ContactResponse,
    ConsentAction,
)
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageIngest,
    ReplyRequest,
    ReplyResponse,
)
from app.schemas.dashboard import (
    DashboardStats,
    ActivitySummary,
    ContactSummary,
)
from app.schemas.settings import (
    SettingsUpdate,
    SettingsResponse,
)
from app.schemas.memory import (
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryItem,
)

__all__ = [
    "TokenPayload",
    "LoginRequest",
    "RegisterRequest",
    "AuthResponse",
    "RefreshRequest",
    "ContactCreate",
    "ContactUpdate",
    "ContactResponse",
    "ConsentAction",
    "MessageCreate",
    "MessageResponse",
    "MessageIngest",
    "ReplyRequest",
    "ReplyResponse",
    "DashboardStats",
    "ActivitySummary",
    "ContactSummary",
    "SettingsUpdate",
    "SettingsResponse",
    "MemorySearchRequest",
    "MemorySearchResponse",
    "MemoryItem",
]