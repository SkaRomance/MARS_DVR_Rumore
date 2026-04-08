"""Application configuration settings."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/mars_noise"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1/noise"
    cors_origins: list[str] = ["http://localhost:3000"]

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str | None = None
    ollama_model: str = "glm-5.1"

    ai_max_tokens: int = 4000
    ai_temperature: float = 0.7
    ai_cache_enabled: bool = True
    ai_confidence_threshold: float = 0.7

    app_version: str = "0.1.0"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
