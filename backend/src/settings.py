from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # NOTE: env_file is intentionally left unset (None) — the container's CWD is
    # /app, not the repo root, so a relative ".env" path would never resolve inside
    # Docker. Configuration is injected entirely via Docker Compose's `env_file:`
    # directive, which populates the process environment before Uvicorn starts.
    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    database_url: str
    session_secret: str
    api_port: int = 8000
    frontend_url: str = "http://localhost:9999"


@lru_cache
def get_settings() -> Settings:
    return Settings()
