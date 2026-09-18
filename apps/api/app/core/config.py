"""Application settings.

Loaded from environment variables (or apps/api/.env) with the VIRAM_ prefix,
e.g. VIRAM_DATABASE_URL. Secrets are never committed; see .env.example.
"""

from functools import lru_cache

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="VIRAM_",
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "VIRAM API"
    ENVIRONMENT: str = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://viram:viram@localhost:5432/viram"

    # --- Auth ---
    JWT_SECRET_KEY: str = "changeme-generate-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    # --- Payments ---
    # DEV/DEMO ONLY: HMAC secret for the clearly-labelled mock gateway's webhook.
    # A real gateway (Razorpay) is selected in non-local environments and fails
    # fast without its own credentials (design doc §18).
    MOCK_WEBHOOK_SECRET: str = "dev-only-mock-webhook-secret"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> object:
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_local(self) -> bool:
        return self.ENVIRONMENT in {"local", "test"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
