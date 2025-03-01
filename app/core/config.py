import secrets
from typing import Any, List, Optional, Union, Dict

from pydantic import AnyHttpUrl, field_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # Server settings
    SERVER_NAME: str = "localhost"
    SERVER_HOST: AnyHttpUrl = "http://localhost:8000"
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

    # Database settings
    SQLALCHEMY_DATABASE_URI: str

    # JWT settings
    JWT_ALGORITHM: str = "HS256"

    # Gamification settings
    BASE_XP_DAILY_QUEST: int = 5
    BASE_XP_REGULAR_QUEST: int = 10
    BASE_XP_EPIC_QUEST: int = 25
    BASE_XP_BOSS_QUEST: int = 50

    # Use SettingsConfigDict instead of Config class
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


# Create settings instance
settings = Settings()
