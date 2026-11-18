"""Konfigurasi dari environment. Kredensial tidak pernah ditulis di source code."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_ROOT / ".env"), extra="ignore"
    )

    # PostgreSQL: satu database "foodsave" dengan skema operational, prediction,
    # model_analysis.
    database_url: str = ""
    database_host: str = "localhost"
    database_port: int = 5432
    postgres_db: str = "foodsave"
    postgres_user: str = "foodsave"
    postgres_password: SecretStr = SecretStr("")

    # Web dan sesi
    cors_origins: str = "http://localhost:3000"
    cookie_secure: bool = False
    session_days: int = 7
    registration_enabled: bool = True

    # Penyimpanan file aplikasi (unggahan CSV dan laporan operasional).
    app_storage_path: Path = PROJECT_ROOT / "storage" / "app"

    # Penyimpanan model (HDFS di Docker). Lihat foodsave_core.storage.
    foodsave_storage: Literal["hdfs", "local"] = "local"
    hdfs_namenode_url: str = "http://namenode:9870"
    hdfs_user: str = "foodsave"
    local_storage_root: Path = PROJECT_ROOT / "storage" / "hdfs"

    # Email laporan (Mailpit lokal)
    mail_backend: Literal["disabled", "mailpit"] = "disabled"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "foodsave@example.test"
    smtp_timeout_seconds: int = 10

    # Ekspor data aktual ke HDFS /foodsave/raw/actuals
    training_export_interval_hours: float = 24.0

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
    def origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
