from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://newtonite:newtonite@localhost:5432/newtonite"
    test_database_url: str = "postgresql+psycopg2://newtonite:newtonite@localhost:5433/newtonite_test"

    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 45

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    idempotency_ttl_hours: int = 24

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        # Hosting providers (Render, Heroku, ...) hand out "postgres://" or
        # "postgresql://" URLs. SQLAlchemy 2.x needs an explicit psycopg2 driver.
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg2://" + value[len("postgres://"):]
        if value.startswith("postgresql://"):
            return "postgresql+psycopg2://" + value[len("postgresql://"):]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
