import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Spry API"
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "info")
    database_url: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/spry"
    )
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,*").split(",")
        if origin.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
