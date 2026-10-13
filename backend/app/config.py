from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: Literal["development", "test", "production"] = "development"
    app_name: str = "Smart Hospital Queue API"
    api_prefix: str = "/api"

    # Google OAuth
    google_client_id: str = ""

    frontend_origin: str = "http://localhost:5173,http://127.0.0.1:5173"
    mongodb_uri: str = "mongodb://localhost:27017/hospital_queue"
    jwt_secret: str = "development-only-change-before-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    ml_api_url: str = "http://127.0.0.1:8001/predict"
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 900
    qr_rate_limit: int = 10
    qr_rate_window_seconds: int = 60

    # SMS Settings (Additive notification layer)
    sms_enabled: bool = False
    sms_provider: str = "fast2sms"
    sms_api_key: str = ""
    sms_sender_id: str = ""
    sms_api_url: str = "https://www.fast2sms.com/dev/bulkV2"

    # Firebase Cloud Messaging Settings
    firebase_service_account_path: str = ""
    firebase_project_id: str = "carepluse-5d705"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    @model_validator(mode="after")
    def reject_insecure_production_settings(self) -> "Settings":
        if (
            self.environment == "production"
            and self.jwt_secret == "development-only-change-before-production"
        ):
            raise ValueError(
                "JWT_SECRET must be set to a unique secret in production"
            )
        return self

    @property
    def frontend_origins(self) -> list[str]:
        """Allow a comma-separated origin list without hard-coding deployments."""
        return [
            origin.strip()
            for origin in self.frontend_origin.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()