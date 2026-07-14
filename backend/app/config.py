from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{BACKEND_ROOT / 'data' / 'starsleep.db'}"
    public_base_url: str = "http://127.0.0.1:8000"

    dify_api_base: str = "https://api.dify.ai/v1"
    dify_api_key: str = ""
    dify_app_id: str = ""

    order_http_timeout_sec: float = 5.0
    order_http_max_retries: int = 2
    order_http_retry_backoff_sec: float = 0.4

    knowledge_dir: str = str(REPO_ROOT / "knowledge-base")


@lru_cache
def get_settings() -> Settings:
    return Settings()
