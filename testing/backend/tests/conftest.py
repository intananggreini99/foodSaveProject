"""Tes integrasi pada PostgreSQL sungguhan dengan model hasil pipeline MLflow sungguhan.

- Database harus bernama *_test (fixture menolak database lain).
- Skema dibuat dari migrasi Alembic, diturunkan lalu dinaikkan lagi.
- Pipeline ml/ dijalankan sekali dalam mode cepat ke penyimpanan lokal yang
  meniru HDFS, lalu model aktifnya dipakai seluruh tes API.
- Setiap tes berjalan di transaksi yang di-rollback.

Jalankan: python backend/run_tests.py   (lihat README)
"""

import os
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent
sys.path.insert(0, str(PROJECT / "ml"))

from app.core import database  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.common import model_storage  # noqa: E402
from app.services.prediction_service import prediction_service  # noqa: E402

PASSWORD = "FoodSave-Test-2026!"


@contextmanager
def inside(folder):
    """MLflow (tracking sqlite) menaruh artefak di ./mlruns: jalankan di folder sementara."""
    previous = os.getcwd()
    os.chdir(folder)
    try:
        yield
    finally:
        os.chdir(previous)


def run_pipeline(prepared):
    from foodsave_ml.pipeline import run

    with inside(prepared["mlflow_dir"]):
        return run(prepared["pipeline_config"], prepared["storage"])


@pytest.fixture(scope="session")
def storage_root(tmp_path_factory):
    return tmp_path_factory.mktemp("hdfs")


@pytest.fixture(scope="session", autouse=True)
def prepared(storage_root, tmp_path_factory):
    url = make_url(get_settings().database_url)
    assert url.get_backend_name() == "postgresql" and url.database.endswith("_test"), (
        "Tes hanya boleh memakai PostgreSQL dengan nama database *_test."
    )
    settings = get_settings()
    settings.foodsave_storage = "local"
    settings.local_storage_root = storage_root
    settings.app_storage_path = tmp_path_factory.mktemp("app")
    settings.mail_backend = "disabled"
    model_storage.cache_clear()

    config = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # aman diulang

    from foodsave_core.storage import RAW_SEED, LocalStorage, ensure_layout
    from foodsave_ml.config import PipelineConfig
    from foodsave_ml.pipeline import run

    storage = LocalStorage(storage_root)
    ensure_layout(storage)
    storage.write_bytes(RAW_SEED, (PROJECT / "dataset/raw/train.csv").read_bytes())
    mlflow_dir = tmp_path_factory.mktemp("mlflow")
    pipeline_config = PipelineConfig(
        tracking_uri=f"sqlite:///{mlflow_dir}/mlflow.db",
        database_url=get_settings().database_url,
        cv_folds=3,
        n_estimators=30,
        permutation_repeats=2,
    )
    pipeline_config.grid = pipeline_config.grid[:2]
    with inside(mlflow_dir):
        summary = run(pipeline_config, storage)
    prediction_service.reset()
    yield {"summary": summary, "storage": storage, "mlflow_dir": mlflow_dir,
           "pipeline_config": pipeline_config}
    engine.dispose()


@pytest.fixture
def factory(monkeypatch):
    connection = engine.connect()
    transaction = connection.begin()
    sessions = sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )

    def override():
        with sessions() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(database, "SessionLocal", sessions)
    monkeypatch.setattr(get_settings(), "mail_backend", "disabled")
    yield sessions
    app.dependency_overrides.clear()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(factory):
    with TestClient(app) as session:
        yield session


def register(client, email="owner@example.test", name="Restoran Uji"):
    result = client.post(
        "/api/v1/auth/register",
        json={"name": "Pemilik Uji", "email": email, "password": PASSWORD, "restaurant_name": name},
    )
    assert result.status_code == 201, result.text
    return result.json()


@pytest.fixture
def owner(client):
    return register(client)


@pytest.fixture
def operation_payload():
    return {
        "operation_date": "2026-11-11",
        "meals_prepared": 400,
        "kitchen_staff": 12,
        "staff_experience": "intermediate",
        "special_event": False,
        "event_type": None,
        "temperature_c": 28,
        "humidity_percent": 65,
        "previous_waste_kg": 20,
        "waste_category": "vegetables",
        "actual_waste_kg": None,
        "manager_notes": "Data pengujian backend.",
    }


def count(factory, table):
    with factory() as db:
        return db.scalar(text(f"SELECT count(*) FROM {table}"))
