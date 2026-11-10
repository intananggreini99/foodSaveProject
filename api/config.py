"""Konfigurasi dari environment; kredensial tidak ditulis di source code."""

from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr, model_validator
from typing import Literal
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = ""
    database_host: str = "localhost"
    database_port: int = 5433
    postgres_db: str = "foodsave"
    postgres_user: str = "foodsave"
    postgres_password: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:3000,http://localhost:8000"
    cookie_secure: bool = False
    session_days: int = 7
    storage_path: Path = ROOT / "storage"
    model_manifest: Path = ROOT / "models/best_model/selected_model.json"
    registration_enabled: bool = True
    mail_backend: Literal["disabled", "mailpit"] = "disabled"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "foodsave@example.test"
    smtp_timeout_seconds: int = 10

    @model_validator(mode="after")
    def build_database_url(self):
        if not self.database_url:
            self.database_url = URL.create(
                "postgresql+psycopg",
                username=self.postgres_user,
                password=self.postgres_password.get_secret_value(),
                host=self.database_host,
                port=self.database_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self

    @property
    def origins(self):
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings():
    return Settings()
