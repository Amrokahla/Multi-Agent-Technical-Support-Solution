"""Application settings, loaded from the environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# ai-operations-platform/  (config.py -> app -> backend -> project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # Load the project .env and, as a fallback, the workspace .env.local (where the
    # OpenAI key lives). Process env vars still take precedence over both.
    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), str(PROJECT_ROOT.parent / ".env.local")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    # Copilot orchestrator: GPT-5 plans (tool selection), GPT-5-mini synthesizes.
    planner_model: str = "gpt-5"
    synth_model: str = "gpt-5-mini"

    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
