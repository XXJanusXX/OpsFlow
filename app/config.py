import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # "ollama" for local inference, or "openai_compatible" for a hosted
    # Chat Completions-compatible endpoint.
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama").lower()
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    compatible_base_url: str = os.getenv("LLM_BASE_URL", "").rstrip("/")
    compatible_api_key: str = os.getenv("LLM_API_KEY", "")
    compatible_model: str = os.getenv("LLM_MODEL", "")
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))
    database_path: str = os.getenv("DATABASE_PATH", "./opsflow.db")


settings = Settings()
