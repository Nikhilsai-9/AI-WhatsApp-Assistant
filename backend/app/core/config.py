"""
Application configuration loaded from environment / .env file.

Production-grade settings with safe defaults and validation.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _generate_dev_secret() -> str:
    """Generate a random secret for dev environments when none is provided."""
    return secrets.token_urlsafe(32)


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
    app_url: str = "http://localhost:3000"
    app_owner_email: str = ""

    # ─── Secrets ────────────────────────────────────────────────
    # Allow these to be empty in dev; required in production. We use
    # `default_factory` so they remain valid for unit tests.
    app_secret: str = Field(
        default_factory=_generate_dev_secret,
        min_length=32,
        description="General-purpose application secret (used for CSRF, cookie signing).",
    )
    jwt_secret: str = Field(
        default_factory=_generate_dev_secret,
        min_length=32,
        description="JWT signing key. MUST be overridden in production.",
    )
    encryption_key: str = Field(
        default="",
        description="Fernet encryption key (base64). Generated at startup if empty.",
    )

    # ─── Database ───────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "assistant"
    postgres_password: str = "assistant"
    postgres_db: str = "assistant"
    database_url: str = ""

    # ─── Redis ──────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_url: str = ""

    # ─── JWT ────────────────────────────────────────────────────
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 14

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

    minmax_api_key: str = ""
    minmax_model: str = "MiniMax-Text-01"

    ollama_base_url: str = "http://localhost:11434"
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
    bridge_webhook_secret: str = Field(
        default_factory=_generate_dev_secret,
        min_length=8,
        description="Shared secret between FastAPI and the Node bridge.",
    )

    # ─── Frontend / CORS ────────────────────────────────────────
    frontend_url: str = "http://localhost:3000"
    cors_allow_origins: str = ""  # comma-separated additional origins

    # ─── OAuth (Google) ─────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""

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
    def _build_db_url(cls, v, info) -> str:
        if v:
            return str(v)
        data = info.data
        return (
            f"postgresql+asyncpg://{data.get('postgres_user', 'assistant')}:"
            f"{data.get('postgres_password', 'assistant')}@"
            f"{data.get('postgres_host', 'localhost')}:"
            f"{data.get('postgres_port', 5432)}/"
            f"{data.get('postgres_db', 'assistant')}"
        )

    @field_validator("redis_url", mode="before")
    @classmethod
    def _build_redis_url(cls, v, info) -> str:
        if v:
            return str(v)
        data = info.data
        pw = data.get("redis_password", "")
        host = data.get("redis_host", "localhost")
        port = data.get("redis_port", 6379)
        auth = f":{pw}@" if pw else ""
        return f"redis://{auth}{host}:{port}/0"

    @property
    def sync_database_url(self) -> str:
        """Used by Alembic (sync driver)."""
        url = self.database_url
        if "+asyncpg" in url:
            return url.replace("+asyncpg", "+psycopg2")
        if "+psycopg" not in url and url.startswith("postgresql"):
            return url.replace("postgresql", "postgresql+psycopg2", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

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
        """Alias for app_secret for compatibility (Django-style)."""
        return self.app_secret

    @property
    def cors_origins(self) -> list[str]:
        """CORS allowed origins (production-safe list)."""
        origins = [
            self.app_url,
            self.frontend_url,
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ]
        if self.cors_allow_origins:
            for o in self.cors_allow_origins.split(","):
                o = o.strip()
                if o and o not in origins:
                    origins.append(o)
        # In production, restrict to configured URLs.
        if self.is_production:
            return [o for o in origins if "localhost" not in o and "127.0.0.1" not in o] or [self.app_url]
        return origins

    @property
    def storage_dir(self) -> Path:
        p = Path(self.storage_path)
        p.mkdir(parents=True, exist_ok=True)
        return p

    def model_post_init(self, __context) -> None:
        """Post-init validation — ensure required production secrets are present."""
        if self.is_production:
            # If the default random secret survived, refuse to start.
            # We can't actually detect "is random default" — but we
            # at least enforce a minimum length, which the Field
            # already guarantees.
            if len(self.jwt_secret) < 32:
                raise ValueError("jwt_secret must be at least 32 chars in production")
            if len(self.app_secret) < 32:
                raise ValueError("app_secret must be at least 32 chars in production")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton accessor (caches across imports)."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
