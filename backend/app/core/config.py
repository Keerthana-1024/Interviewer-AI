"""Application configuration using pydantic-settings."""
from functools import lru_cache
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database (Supabase PostgreSQL)
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/interview_ai"
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # LLM (Ollama by default)
    LLM_PROVIDER: str = "ollama"  # ollama | openai | anthropic | google | mock
    LLM_MODEL: str = "qwen2.5:7b-instruct-q4_0"
    LLM_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_RETRIES: int = 3

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # Deepgram TTS
    DEEPGRAM_API_KEY: str = ""

    # File upload
    MAX_FILE_SIZE_MB: int = 10

    # App
    SECRET_KEY: str = "dev-secret-key-replace-in-production"
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # Interview defaults
    DEFAULT_INTERVIEW_DURATION_MINUTES: int = 30
    DEFAULT_MAX_QUESTIONS: int = 12
    DEFAULT_MAX_FOLLOW_UPS_PER_TOPIC: int = 2

    # Matching weights (must sum to 1.0)
    WEIGHT_REQUIRED_SKILL_COVERAGE: float = 0.45
    WEIGHT_EVIDENCE_STRENGTH: float = 0.25
    WEIGHT_SEMANTIC_RELEVANCE: float = 0.20
    WEIGHT_EXPERIENCE_ALIGNMENT: float = 0.10

    # Fuzzy matching threshold
    FUZZY_MATCH_THRESHOLD: int = 80

    # Miro (board ID route — no per-user OAuth needed)
    MIRO_ACCESS_TOKEN: str = ""
    MIRO_BOARD_ID: str = ""

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",")]

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
