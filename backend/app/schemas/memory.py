"""Memory schemas."""

from __future__ import annotations

from pydantic import BaseModel


class MemorySearchRequest(BaseModel):
    query: str
    contact_id: str | None = None
    limit: int = 5
    memory_type: str | None = None


class MemoryItem(BaseModel):
    id: str
    content: str
    summary: str | None
    memory_type: str
    importance_score: float
    access_count: int
    created_at: str

    model_config = {"from_attributes": True}


class MemorySearchResponse(BaseModel):
    results: list[MemoryItem]
    total: int