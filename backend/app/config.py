"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://zotta:zotta_secret@localhost:5432/zotta"
    )
    database_url_sync: str = Field(
        default="postgresql://zotta:zotta_secret@localhost:5432/zotta"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # JWT
    secret_key: str = Field(default="change-me-to-a-random-secret-key-in-production")
    access_token_expire_minutes: int = Field(default=60)
    refresh_token_expire_days: int = Field(default=7)

    # CORS
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000")

    # Credit Bureau
    credit_bureau_provider: str = Field(default="mock")
    av_knowles_api_url: str = Field(default="")
    av_knowles_api_key: str = Field(default="")

    # ID Verification
    id_verification_provider: str = Field(default="mock")

    # Twilio
    twilio_account_sid: str = Field(default="")
    twilio_auth_token: str = Field(default="")
    twilio_whatsapp_number: str = Field(default="whatsapp:+14155238886")

    # OpenAI
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    # File Storage
    upload_dir: str = Field(default="./uploads")
    max_upload_size_mb: int = Field(default=10)

    # Environment
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
