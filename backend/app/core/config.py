"""
Centralized application configuration.

Everything that can vary between environments (DB, providers, secrets,
retrieval tuning) is read from environment variables via pydantic-settings.
Nothing here hard-codes an API key, a vendor, or a "magic" ranking weight --
those are all overridable through .env so the system is configurable per
Section 10/11/18 of the spec.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_ENV: str = "development"
    APP_NAME: str = "resume-intelligence-backend"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "http://localhost:3000"

    # --- Database ---
    # Defaults to a local SQLite file so the project runs with zero external
    # services for evaluation/demo purposes. Point this at
    # postgresql+asyncpg://... with pgvector installed for production /
    # 10,000+ resume scale (see docs/DATABASE.md).
    DATABASE_URL: str = "sqlite+aiosqlite:///./resume_intel.db"
    DATABASE_ECHO: bool = False
    VECTOR_DIMENSION: int = 384  # must match the active embedding provider's output dim

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False  # set True for tests / no-Redis dev runs

    # --- Auth ---
    JWT_SECRET_KEY: Optional[str] = None
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_MINUTES: int = 60 * 24 * 7
    OTP_EXPIRE_MINUTES: int = 10
    OTP_LENGTH: int = 6

    # --- Rate limiting ---
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_OTP_PER_MINUTE: int = 3

    # --- File upload ---
    MAX_UPLOAD_MB: int = 15
    MAX_BULK_FILES: int = 100
    MAX_BULK_UPLOAD_MB: int = 250
    ALLOWED_RESUME_TYPES: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "text/plain"
    )
    UPLOAD_DIR: str = "./data/uploads"

    # --- LLM provider ---
    LLM_PROVIDER: Literal["openai", "keygateway", "local", "none"] = "keygateway"
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://keygateway1.arshnivlabs.com/v1"
    LLM_TIMEOUT_SECONDS: float = 30.0
    LLM_MAX_RETRIES: int = 2
    LLM_TEMPERATURE: float = 0.2
    LLM_FALLBACK_PROVIDER: Literal["local", "none"] = "none"

    # --- Embedding provider ---
    # "local" = sentence-transformers (or hashing fallback if the model
    # can't be downloaded); "keygateway" = OpenAI-compatible /embeddings
    # endpoint on the same gateway as the LLM.
    EMBEDDING_PROVIDER: Literal["local", "keygateway"] = "local"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_FALLBACK_PROVIDER: Literal["local_hashing", "none"] = "local_hashing"

    # --- Reranker provider ---
    # No verified reranking endpoint exists on the KeyGateway (see README's
    # "KeyGateway capability notes"), so the only real implementation is
    # local. The abstraction still exists so a vendor reranker can be added
    # later without touching calling code.
    RERANKER_PROVIDER: Literal["local", "none"] = "local"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Retrieval tuning ---
    RETRIEVAL_CANDIDATE_POOL_SIZE: int = 100  # hybrid retrieval -> this many go to reranker
    RETRIEVAL_RERANK_TOP_K: int = 20          # reranker -> this many go to deep agent analysis
    RETRIEVAL_TOP_K: int = 5                  # default Top-N returned to HR (3 or 5, request-overridable)
    RETRIEVAL_SIMILARITY_THRESHOLD: float = 0.15
    HYBRID_LEXICAL_WEIGHT: float = 0.4
    HYBRID_SEMANTIC_WEIGHT: float = 0.6

    # --- Email ---
    EMAIL_PROVIDER: Literal["smtp", "console"] = "console"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "no-reply@resume-intel.local"
    SMTP_USE_TLS: bool = True

    # --- Demo bootstrap ---
    BOOTSTRAP_ADMIN_EMAIL: Optional[str] = None
    BOOTSTRAP_ADMIN_PASSWORD: Optional[str] = None

    @model_validator(mode="after")
    def require_jwt_secret(self):
        if not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be configured before starting the application.")
        if self.APP_ENV.lower() in {"prod", "production"}:
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("Production requires JWT_SECRET_KEY to be configured with at least 32 characters.")
            if self.JWT_SECRET_KEY.startswith("CHANGE-ME"):
                raise ValueError("Production JWT_SECRET_KEY cannot use an example placeholder.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
