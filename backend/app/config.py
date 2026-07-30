from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://mypost:change-me@db/mypost"
    secret_key: str = "development-only-secret-change-me"
    base_path: str = "/mail"
    sync_interval_seconds: int = 120
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache
def get_settings() -> Settings: return Settings()
settings = get_settings()

