from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "AI Gateway"
    debug: bool = False

    # Security
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Database
    # WORK LAPTOP: SQLite (no Docker needed — stored in ./gateway_dev.db)
    # PERSONAL LAPTOP: switch to postgresql+asyncpg://gateway:gateway@localhost:5432/gateway
    database_url: str = "sqlite+aiosqlite:///./gateway_dev.db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # ChromaDB / semantic cache
    # WORK LAPTOP: ChromaDB query segfaults on Python 3.14 + Windows — keep False.
    # PERSONAL LAPTOP: set ENABLE_SEMANTIC_CACHE=true after verifying chromadb works.
    enable_semantic_cache: bool = False
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_collection: str = "prompt_cache"
    cache_similarity_threshold: float = 0.95
    cache_ttl_hours: int = 24

    # LLM Providers
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"   # override in .env to use OpenRouter
    gemini_api_key: str = ""

    # Primary and fallback model
    primary_model: str = "gpt-4o-mini"
    fallback_model: str = "gemini/gemini-1.5-flash"

    # Smart routing (Phase 1)
    enable_smart_routing: bool = False
    cheap_model: str = "gpt-4o-mini"
    premium_model: str = "gpt-4o"

    # Prompt compression (Phase 2)
    enable_prompt_compression: bool = False
    compression_threshold_tokens: int = 1500

    # Rate limiting (tokens per minute per tier)
    rate_limit_free: int = 10_000
    rate_limit_pro: int = 100_000
    rate_limit_enterprise: int = 1_000_000

    model_config = ConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
