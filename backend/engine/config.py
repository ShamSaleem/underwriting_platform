"""Runtime configuration, loaded from environment / .env."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UW_", env_file=".env", extra="ignore")

    # Read directly (no UW_ prefix) so it matches the standard SDK env var.
    anthropic_api_key: str | None = None

    model: str = "claude-opus-4-8"
    max_rating_pct: int = 300
    max_tokens: int = 8000

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


def _load() -> Settings:
    import os

    s = Settings()
    # ANTHROPIC_API_KEY has no UW_ prefix; pick it up explicitly.
    s.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY") or s.anthropic_api_key
    return s


settings = _load()
