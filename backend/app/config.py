from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]  # ai-study/


class Settings(BaseSettings):
    # Load the documented backend/.env location. The repository ships only .env.example;
    # real credentials should stay local and must never be committed.
    model_config = SettingsConfigDict(
        env_file=ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Ollama
    ollama_host: str = "http://localhost:11434"
    llm_model: str = "qwen3:4b"          # fits a 6 GB GPU; use gemma2:2b if tight
    vision_model: str = "llava:7b"        # pull separately with: ollama pull llava:7b
    embed_model: str = "bge-m3"            # MUST match the model used in build_index.py
    llm_timeout_s: float = 90.0
    keep_alive: str = "30m"                # keep model in memory between requests
    num_ctx: int = 4096
    max_new_tokens: int = 400
    temperature: float = 0.2
    max_concurrent_llm: int = 2

    # Retrieval
    chroma_path: Path = ROOT / "data" / "chroma_db"
    collection: str = "ncert"
    top_k: int = 4
    min_score: float = 0.45                # confidence threshold, tune with evaluation/
    max_context_chars: int = 6000

    # Online layer
    web_search_enabled: bool = True

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()