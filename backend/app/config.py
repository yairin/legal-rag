from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Look for .env next to backend/ or in backend/ itself
_HERE = Path(__file__).resolve().parent.parent  # backend/
_ENV_FILE = next(
    (p for p in [_HERE / ".env", _HERE.parent / ".env"] if p.exists()),
    _HERE.parent / ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_ignore_empty=True,  # OS empty-string env vars don't override .env file
        extra="ignore",
    )

    # --- AI providers ---
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    voyage_api_key: str = Field(..., alias="VOYAGE_API_KEY")
    cohere_api_key: str = Field(..., alias="COHERE_API_KEY")
    tavily_api_key: str = Field(..., alias="TAVILY_API_KEY")

    # --- Azure DI (optional — falls back to PyMuPDF if empty) ---
    azure_di_endpoint: str = Field("", alias="AZURE_DI_ENDPOINT")
    azure_di_key: str = Field("", alias="AZURE_DI_KEY")

    # --- Qdrant ---
    qdrant_url: str = Field(..., alias="QDRANT_URL")
    qdrant_api_key: str = Field(..., alias="QDRANT_API_KEY")
    collection_name: str = Field("legal_he", alias="COLLECTION_NAME")

    # --- Turnstile ---
    turnstile_secret: str = Field("", alias="TURNSTILE_SECRET")

    # --- Limits ---
    daily_token_budget: int = Field(500_000, alias="DAILY_TOKEN_BUDGET")
    confidence_threshold: float = Field(0.55, alias="CONFIDENCE_THRESHOLD")
    rerank_top_k: int = Field(6, alias="RERANK_TOP_K")
    bm25_top_k: int = Field(30, alias="BM25_TOP_K")

    # --- Models ---
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-6"
    opus_model: str = "claude-opus-4-7"

    # --- Misc ---
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    environment: str = Field("development", alias="ENVIRONMENT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
