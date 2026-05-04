from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama.lan:11434")
DEFAULT_CHAT_MODEL = os.environ.get("DEFAULT_CHAT_MODEL", "medgemma:27b")
BACKEND_API_KEY = os.environ.get("BACKEND_API_KEY")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://llm-agent-qdrant:6333")
SEARXNG_BASE_URL = os.environ.get("SEARXNG_BASE_URL", "http://searxng:8080")

class Settings(BaseSettings):
    app_name: str = "llm-agent"
    env: str = "dev"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    backend_api_key: str = BACKEND_API_KEY
    allow_origins: str = "*"

    ollama_base_url: str = OLLAMA_BASE_URL
    default_chat_model: str = DEFAULT_CHAT_MODEL
    embedding_model: str = "nomic-embed-text:latest"
    model_temperature: float = 0.0
    health_coach_model: str = os.environ.get("HEALTH_COACH_MODEL", DEFAULT_CHAT_MODEL)
    health_coach_days: int = int(os.environ.get("HEALTH_COACH_DAYS", "30"))

    max_iterations: int = 4
    max_actions_per_iteration: int = 6
    max_web_results: int = 5
    max_rag_results: int = 5
    max_workspace_results: int = 20
    max_scrape_chars: int = 12000
    max_evidence_items: int = 12
    show_trace_in_response: bool = True
    allow_private_network_scraping: bool = False

    qdrant_url: str = QDRANT_URL
    qdrant_collection: str = "documents"
    searxng_base_url: str = SEARXNG_BASE_URL
    http_timeout_seconds: float = 30.0

    workspace_root: Path = Field(default=Path("/workspace"))
    data_dir: Path = Field(default=Path("/data"))
    upload_dir: Path = Field(default=Path("/data/uploads"))
    checkpoint_db_path: Path = Field(default=Path("/data/langgraph-checkpoints.sqlite"))
    state_db_path: Path = Field(default=Path("/data/app.sqlite"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
