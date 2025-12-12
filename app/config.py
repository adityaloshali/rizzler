"""
Configuration management using Pydantic Settings.
Supports environment variables and .env files.
Deployment-agnostic: works with Coolify, Render, Railway, Docker, etc.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    All deployment platforms inject env vars, so this works everywhere.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =========================================
    # Application
    # =========================================
    app_name: str = "Rizzler"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    secret_key: str = Field(default="change-me-in-production")

    # Server
    host: str = "0.0.0.0"
    port: int = Field(default=8000, alias="PORT")  # Render/Railway use PORT
    workers: int = 1

    # CORS
    cors_origins: str = "http://localhost:3000"

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # =========================================
    # Database - Supabase
    # =========================================
    supabase_url: str = ""
    supabase_public_key: str = ""
    supabase_secret_key: str = ""

    # Direct Postgres (SQLAlchemy)
    database_url: str = Field(default="", alias="DATABASE_URL")

    @computed_field
    @property
    def async_database_url(self) -> str:
        """Ensure we use asyncpg driver."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # =========================================
    # AI/LLM Providers
    # =========================================
    openai_api_key: str = ""
    google_api_key: str = ""
    openrouter_api_key: str = ""

    # =========================================
    # Model Configuration
    # =========================================
    # Embeddings
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # Tutor/Analysis (safe, multimodal)
    tutor_model: str = "gemini-1.5-flash"
    tutor_provider: Literal["google", "openai"] = "google"

    # Practice (uncensored)
    practice_model: str = "mythomax-l2-13b"
    practice_provider: Literal["openrouter"] = "openrouter"

    # =========================================
    # Redis
    # =========================================
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # =========================================
    # Storage
    # =========================================
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    @computed_field
    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # =========================================
    # Computed / Helpers
    # =========================================
    @computed_field
    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @computed_field
    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings instance.
    Use dependency injection in FastAPI: Depends(get_settings)
    """
    return Settings()


# Convenience export
settings = get_settings()

