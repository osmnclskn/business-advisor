from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )
    openai_api_key: str
    anthropic_api_key: str
    google_api_key: str
    tavily_api_key: str
    tavily_polling_interval: int = 3
    tavily_max_polling_attempts: int = 60
    discovery_min_questions: int = 3
    discovery_max_questions: int = 5
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "business_advisor"
    redis_url: str = "redis://localhost:6379/0"
    session_ttl_seconds: int = 3600
    app_env: str = "development"  # development, production, testing
    debug: bool = True
    log_level: str = "INFO"
    rate_limit_per_minute: int = 500
    rate_limit_execute: str = "20/minute"
    rate_limit_tasks: str = "60/minute"
    rate_limit_sessions: str = "30/minute"


@lru_cache
def get_settings() -> Settings:
    return Settings()
