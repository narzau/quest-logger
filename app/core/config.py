# app/core/config.py
import secrets
from typing import Any, List, Optional, Union, Dict, Literal

from pydantic import AnyHttpUrl, field_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Environment settings
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"

    # API settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Server settings
    SERVER_NAME: str = "localhost"
    SERVER_HOST: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"  # Frontend URL for share links

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost",
        "http://localhost:4200",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FILE: Optional[str] = None  # Path to log file if file logging is enabled

    # Database settings
    SQLALCHEMY_DATABASE_URI: str

    # JWT settings
    JWT_ALGORITHM: str = "HS256"

    # Gamification settings
    BASE_XP_DAILY_QUEST: int = 5
    BASE_XP_REGULAR_QUEST: int = 10
    BASE_XP_EPIC_QUEST: int = 25
    BASE_XP_BOSS_QUEST: int = 50

    # API Call Timeouts (in seconds)
    DEFAULT_TIMEOUT: int = 30
    LLM_TIMEOUT: int = 60
    STT_TIMEOUT: int = 120

    # Speech-to-Text settings
    DEFAULT_STT_PROVIDER: str = "deepgram"  # Default provider

    # Provider-specific settings
    # Deepgram
    DEEPGRAM_API_KEY: str

    # OpenRouter for LLM
    OPENROUTER_API_KEY: str
    OPENROUTER_API_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = (
        "mistralai/mistral-7b-instruct"  # Default model for quest parsing
    )

    # Feature flags
    ENABLE_LLM_FEATURES: bool = True
    ENABLE_VOICE_FEATURES: bool = True
    ENABLE_TRANSLATION: bool = True

    # Google
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_CLIENT_SECRETS_JSON: str = ""

    # Subscription Settings
    STRIPE_API_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRO_PRICE_ID: Optional[str] = None

    # Use SettingsConfigDict instead of Config class
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


# Create settings instance
settings = Settings()
