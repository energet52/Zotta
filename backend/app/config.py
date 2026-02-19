"""
Application configuration — single source of truth.

All environment variables are defined in the root .env file.
This module loads them via pydantic-settings and exposes a singleton `settings`.
"""

import secrets
import logging
import warnings
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

_config_logger = logging.getLogger("zotta.config")

# Resolve paths relative to repo root (two levels up from this file)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # backend/app/config.py → repo root
_ENV_FILE = _REPO_ROOT / ".env"


class Settings(BaseSettings):
    # ── General ──────────────────────────────────────────────
    environment: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # ── Database ─────────────────────────────────────────────
    postgres_user: str = Field(default="zotta")
    postgres_password: str = Field(default="zotta_secret")
    postgres_db: str = Field(default="zotta")
    database_url: str = Field(
        default="postgresql+asyncpg://zotta:zotta_secret@localhost:5432/zotta"
    )
    database_url_sync: str = Field(
        default="postgresql://zotta:zotta_secret@localhost:5432/zotta"
    )

    # ── Redis ────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0")

    # ── JWT Authentication ───────────────────────────────────
    secret_key: str = Field(default="")
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=7)

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    # ── Credit Bureau ────────────────────────────────────────
    credit_bureau_provider: str = Field(default="mock")
    av_knowles_api_url: str = Field(default="")
    av_knowles_api_key: str = Field(default="")
    av_knowles_web_url: str = Field(default="")
    av_knowles_username: str = Field(default="")
    av_knowles_password: str = Field(default="")

    # ── ID Verification ──────────────────────────────────────
    id_verification_provider: str = Field(default="mock")

    # ── Twilio (WhatsApp) ────────────────────────────────────
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_whatsapp_number: str = Field(default="whatsapp:+14155238886")
    whatsapp_sandbox_phone: str = Field(
        default="",
        description="Override recipient for WhatsApp in non-production environments",
    )

    # ── OpenAI ───────────────────────────────────────────────
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    # ── File Storage ─────────────────────────────────────────
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=10)

    # ── Lender / Company Info ────────────────────────────────
    lender_name: str = Field(default="Zotta")
    lender_address: str = Field(
        default="No. 3 The Summit, St. Andrews Wynd Road, Moka, Maraval, Trinidad and Tobago"
    )

    # ── Customer Support Chat Timeouts ───────────────────────
    conversation_nudge_minutes: int = Field(default=5, description="Send nudge when borrower silent")
    conversation_save_summary_minutes: int = Field(default=30)
    conversation_followup_1_days: int = Field(default=1)
    conversation_followup_2_days: int = Field(default=3)
    conversation_expire_days: int = Field(default=7)

    # ── Frontend ─────────────────────────────────────────────
    vite_api_url: str = Field(default="")

    @model_validator(mode="after")
    def _enforce_secret_key(self) -> "Settings":
        """In production the SECRET_KEY env var is mandatory.
        In development a random key is generated and a warning is emitted."""
        placeholder = "change-me-to-a-random-secret-key-in-production"
        if not self.secret_key or self.secret_key == placeholder:
            if self.environment != "development":
                raise ValueError(
                    "SECRET_KEY environment variable must be set in non-development environments. "
                    "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
                )
            self.secret_key = secrets.token_urlsafe(64)
            warnings.warn(
                "SECRET_KEY not set — auto-generated a random key for development. "
                "Sessions will not persist across restarts.",
                stacklevel=2,
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
