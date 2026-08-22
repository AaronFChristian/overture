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
        default="postgresql://overture:overture@localhost:5432/overture",
        description="Postgres connection string, pgvector extension required.",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance.

    lru_cache means Settings() is constructed once per process, not once
    per request — env parsing and validation happen a single time at
    first access, and every caller after that gets the same instance.
    """
    return Settings()
