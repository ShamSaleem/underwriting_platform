"""Runtime configuration, loaded from environment / .env.

LLM provider is Google Gemini. Set GEMINI_API_KEY (free key from aistudio.google.com)
to enable the AI assessor; without it the app runs rules-only. UW_LLM_ENABLED is a
kill switch to force the LLM off even when a key is present.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UW_", env_file=".env", extra="ignore")

    # Read directly (no UW_ prefix) to match the standard env var name.
    gemini_api_key: str | None = None

    gemini_model: str = "gemini-2.5-flash-lite"
    llm_enabled_flag: bool = True   # UW_LLM_ENABLED_FLAG — kill switch
    max_rating_pct: int = 300
    llm_timeout_seconds: float = 25.0

    @property
    def llm_enabled(self) -> bool:
        return bool(self.gemini_api_key) and self.llm_enabled_flag

    @property
    def model(self) -> str:
        return self.gemini_model


def _load() -> Settings:
    import os

    # Load backend/.env into the process environment so the no-prefix keys below
    # (GEMINI_API_KEY / GOOGLE_API_KEY) are visible to os.environ.
    try:
        from dotenv import load_dotenv
        from pathlib import Path

        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except Exception:
        pass

    s = Settings()
    # GEMINI_API_KEY / GOOGLE_API_KEY have no UW_ prefix; pick them up explicitly.
    s.gemini_api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or s.gemini_api_key
    )
    if os.environ.get("UW_LLM_ENABLED", "").lower() in ("0", "false", "no"):
        s.llm_enabled_flag = False
    return s


settings = _load()
