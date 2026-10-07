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
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,*"
        ).split(",")
        if origin.strip()
    ]

    cognito_region: str = os.getenv("COGNITO_REGION", "eu-north-1")
    cognito_user_pool_id: str = os.getenv("COGNITO_USER_POOL_ID", "")
    cognito_client_id: str = os.getenv("COGNITO_CLIENT_ID", "")
    cognito_jwks: str = os.getenv("COGNITO_JWKS", "")

    @property
    def cognito_issuer(self) -> str:
        return (
            os.getenv("COGNITO_ISSUER")
            or f"https://cognito-idp.{self.cognito_region}.amazonaws.com/{self.cognito_user_pool_id}"
        )

    @property
    def auth_configured(self) -> bool:
        return bool(self.cognito_user_pool_id and self.cognito_client_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
