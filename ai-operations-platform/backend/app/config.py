"""Application settings, loaded from the environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ai-operations-platform/  (config.py -> app -> backend -> project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Operations Platform"
    environment: str = "development"

    # Frozen Zendesk store (source of truth). Override with DATA_DIR.
    data_dir: Path = PROJECT_ROOT / "data" / "raw" / "zendesk"
    # Workforce layer (agents, shifts, contracts) and regenerable analysis outputs.
    wfm_dir: Path = PROJECT_ROOT / "data" / "raw" / "wfm"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    profiles_dir: Path = PROJECT_ROOT / "data" / "processed" / "profiles"

    # AI providers (embeddings, clustering labels, copilot).
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    embedding_model: str = "text-embedding-3-small"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
