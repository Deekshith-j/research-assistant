"""Central configuration.

Every tunable value lives here and is read from environment variables (loaded
from `.env`). Secrets such as API keys are never hard-coded; they only come
from the environment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root = folder that contains this package. All relative paths hang off it,
# so the app works no matter which directory it is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load `.env` once at import time. Existing environment variables win, which lets
# CI or a shell override values without editing the file.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _env_int(name: str, default: int) -> int:
    """Read an integer env var, falling back to `default` when unset or invalid."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Immutable bundle of settings used across the app."""

    # --- Generation model (Groq) -------------------------------------------
    groq_api_key: str | None
    # Strong model for the agents that write and check answers.
    main_model: str
    # Cheaper/faster model for routing and memory extraction (also the fallback).
    fast_model: str
    llm_max_retries: int
    llm_timeout_s: int

    # --- Local knowledge base ----------------------------------------------
    corpus_path: Path
    chroma_dir: Path
    embedding_model: str
    retrieval_top_k: int

    # --- Memory / conversations --------------------------------------------
    db_path: Path
    history_turns: int  # how many recent messages are given to the planner
    max_memories_in_context: int


def load_settings() -> Settings:
    """Build a Settings object from the current environment."""
    storage = PROJECT_ROOT / "storage"
    return Settings(
        groq_api_key=os.getenv("GROQ_API_KEY") or None,
        main_model=os.getenv("GROQ_MAIN_MODEL", "openai/gpt-oss-120b"),
        fast_model=os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b"),
        llm_max_retries=_env_int("LLM_MAX_RETRIES", 4),
        llm_timeout_s=_env_int("LLM_TIMEOUT_S", 60),
        corpus_path=PROJECT_ROOT / "data" / "corpus.jsonl",
        chroma_dir=Path(os.getenv("CHROMA_DIR", storage / "chroma")),
        embedding_model=os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5"),
        retrieval_top_k=_env_int("RETRIEVAL_TOP_K", 8),
        db_path=Path(os.getenv("APP_DB_PATH", storage / "assistant.db")),
        history_turns=_env_int("HISTORY_TURNS", 6),
        max_memories_in_context=_env_int("MAX_MEMORIES_IN_CONTEXT", 12),
    )


# Module-level singleton: import `settings` anywhere instead of re-reading env vars.
settings = load_settings()
