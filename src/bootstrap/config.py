"""Application configuration settings."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/mars_noise"
    redis_url: str = "redis://localhost:6379/0"
    app_env: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1/noise"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    cors_headers: list[str] = ["Content-Type", "Authorization", "X-Request-ID"]

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str | None = None
    ollama_model: str = "glm-5.1:cloud"

    ai_max_tokens: int = 750
    ai_temperature: float = 0.3
    ai_cache_enabled: bool = True
    ai_confidence_threshold: float = 0.7

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7

    app_version: str = "0.1.0"

    keygen_api_url: str = "https://api.keygen.sh/v1"
    keygen_account_id: str = ""
    keygen_product_id: str = ""
    keygen_admin_token: str = ""
    license_grace_period_hours: int = 24

    # ── MARS integration (Wave 26) ──
    mars_api_base_url: str = "http://localhost:5000"
    mars_jwks_url: str = ""
    mars_issuer: str = "mars-core"
    mars_audience: str = "mars-module-noise"
    mars_jwt_algorithm: str = "RS256"
    mars_jwt_hs256_secret: str = ""
    mars_jwks_cache_ttl_seconds: int = 3600
    mars_tenant_cache_ttl_seconds: int = 300
    mars_webhook_secret: str = ""
    mars_http_timeout_seconds: float = 30.0
    mars_http_max_retries: int = 3
    mars_module_key: str = "noise"

    # ── Scheduler (Wave 28) ──
    scheduler_enabled: bool = False
    scheduler_timezone: str = "Europe/Rome"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        if self.app_env != "development" and (
            not self.jwt_secret_key or self.jwt_secret_key == "change-me-in-production"
        ):
            raise ValueError("JWT_SECRET_KEY must be set in production. Set JWT_SECRET_KEY environment variable.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
