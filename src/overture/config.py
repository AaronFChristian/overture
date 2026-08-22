"""Application configuration.

Every setting the app needs is declared here as a typed field. Nothing
else in the codebase should call `os.environ` directly — importing
`get_settings()` is the only sanctioned way to read config. This keeps
every setting discoverable in one place and gives us validation for
free: a missing required value fails at startup, not three requests in.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "overture"
    environment: Literal["local", "staging", "production"] = "local"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    database_url: str = Field(
        default="postgresql+asyncpg://overture:overture@localhost:5432/overture",
        description="Postgres connection string, pgvector extension required. "
        "Must use the asyncpg driver — the ORM layer is async end to end.",
    )

    # --- LLM provider selection -------------------------------------------
    # Claude is primary. Azure OpenAI is a swappable second backend behind
    # the same interface (see providers/base.py) — see decisions.md D-0006.
    llm_provider: Literal["anthropic", "azure_openai"] = "anthropic"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"

    azure_openai_api_key: str | None = None
    azure_openai_endpoint: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance.

    lru_cache means Settings() is constructed once per process, not once
    per request — env parsing and validation happen a single time at
    first access, and every caller after that gets the same instance.
    """
    return Settings()
