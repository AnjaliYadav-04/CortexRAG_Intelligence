"""Centralised settings loaded from environment / .env file."""

from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenAI
    OPENAI_API_KEY: str = ""

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "k8s_docs"

    # PostgreSQL
    POSTGRES_DSN: str = "postgresql://rag:rag@localhost:5432/ragdb"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Tavily
    TAVILY_API_KEY: str = ""

    # JWT
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # App behaviour
    LOG_LEVEL: str = "INFO"
    RATE_LIMIT_PER_MIN: int = 20
    TOKEN_BUDGET_PER_DAY: int = 100_000

    # RAG thresholds
    CRAG_RELEVANCE_THRESHOLD: float = 0.7
    SELF_RAG_SCORE_THRESHOLD: float = 0.8
    SELF_RAG_MAX_RETRIES: int = 2

    # Models
    LLM_MODEL: str = "gpt-4o"
    EMBED_MODEL: str = "text-embedding-3-small"
    EMBED_DIM: int = 1536


settings = Settings()
