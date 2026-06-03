"""
IDKP Backend — application settings loaded from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = "IDKP Backend"
    DEBUG: bool = True
    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://idkp:idkp_secret@localhost:5432/idkp"

    # ── Redis ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Auth (Auth.js v5 / NextAuth) ─────────────────────────────
    AUTH_SECRET: str = "change-me-in-production"
    AUTH_TRUST_HOST: bool = True

    # ── Modal.com ────────────────────────────────────────────────
    MODAL_TOKEN_ID: str = ""
    MODAL_TOKEN_SECRET: str = ""

    # ── AWS S3 ───────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "idkp-documents-dev"

    # ── Qdrant ───────────────────────────────────────────────────
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""

    # ── Langfuse ─────────────────────────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3001"


settings = Settings()
