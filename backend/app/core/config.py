"""
Application configuration loaded from environment / .env file.

We use ``pydantic-settings`` so every field is strictly typed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production-grade application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── General ────────────────────────────────────────────────
    app_name: str = "ai-whatsapp-assistant"
    app_version: str = "1.0.0"
    app_env: Literal["development", "production", "test"] = "production"
    app_debug: bool = False
    app_timezone: str = "Asia/Kolkata"
    app_url: str = "http://localhost"
    app_secret: str = Field(default="dev-secret-key-change-in-production-32chars", min_length=32)
    app_owner_email: str = "owner@example.com"
    app_owner_password: str = "change_me_at_first_login"

    # ─── Database ───────────────────────────────────────────────
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "assistant"
    postgres_password: str = "assistant"
    postgres_db: str = "assistant"
    database_url: str = ""

    # ─── Redis ──────────────────────────────────────────────────
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""

    # ─── JWT ────────────────────────────────────────────────────
    jwt_secret: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 14

    # ─── Encryption (Fernet) ───────────────────────────────────
    encryption_key: str = ""

    # ─── AI provider ────────────────────────────────────────────
    ai_provider: Literal[
        "gemini", "openai", "anthropic", "openrouter", "minimax", "ollama"
    ] = "gemini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-latest"

    openrouter_api_key: str = ""
    openrouter_model: str = "anthropic/claude-3.5-sonnet"

    minimax_api_key: str = ""
    minimax_model: str = "MiniMax-Text-01"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1"

    # ─── Embeddings ─────────────────────────────────────────────
    embedding_provider: Literal["sentence_transformers", "openai", "gemini"] = (
        "sentence_transformers"
    )
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ─── Storage ────────────────────────────────────────────────
    storage_backend: Literal["local", "s3"] = "local"
    storage_path: str = "/data/media"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # ─── WhatsApp bridge ────────────────────────────────────────
    bridge_url: str = "http://whatsapp-bridge:3001"
    bridge_webhook_secret: str = ""

    # ─── Logging / observability ────────────────────────────────
    log_level: str = "INFO"
    sentry_dsn: str = ""

    # ─── SMTP ───────────────────────────────────────────────────
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    # ─── Derived helpers ────────────────────────────────────────
    @field_validator("database_url", mode="before")
    @classmethod
    def _build_db_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        return (
            f"postgresql+asyncpg://{data['postgres_user']}:{data['postgres_password']}"
            f"@{data['postgres_host']}:{data['postgres_port']}/{data['postgres_db']}"
        )

    @field_validator("redis_url", mode="before")
    @classmethod
    def _build_redis_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        auth = f":{data['redis_password']}@" if data.get("redis_password") else ""
        return f"redis://{auth}{data['redis_host']}:{data['redis_port']}/0"

    @property
    def sync_database_url(self) -> str:
        """Used by Alembic (sync driver)."""
        return self.database_url.replace("+asyncpg", "+psycopg2")

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def version(self) -> str:
        """Alias for app_version for compatibility."""
        return self.app_version

    @property
    def environment(self) -> str:
        """Alias for app_env for compatibility."""
        return self.app_env

    @property
    def secret_key(self) -> str:
        """Alias for app_secret for compatibility."""
        return self.app_secret

    @property
    def cors_origins(self) -> list[str]:
        """CORS allowed origins."""
        if self.app_env == "production":
            return [self.app_url]
        return ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]

    @property
    def storage_dir(self) -> Path:
        p = Path(self.storage_path)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor (caches across imports)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
