"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/mars_noise"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1/noise"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str | None = None
    ollama_model: str = "glm-5.1"

    ai_max_tokens: int = 750
    ai_temperature: float = 0.3
    ai_cache_enabled: bool = True
    ai_confidence_threshold: float = 0.7

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    app_version: str = "0.1.0"

    keygen_api_url: str = "https://api.keygen.sh/v1"
    keygen_account_id: str = ""
    keygen_product_id: str = ""
    keygen_admin_token: str = ""
    license_grace_period_hours: int = 24

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
