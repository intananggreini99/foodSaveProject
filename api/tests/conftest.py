"""Tes integrasi pada PostgreSQL sungguhan, dengan rollback per tes.

Jalankan melalui python -m api.test_backend agar URL *_test disiapkan otomatis.
Fixture menolak database yang namanya tidak diakhiri _test.
"""

from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from api.config import ROOT, get_settings
from api.database import engine, get_db
from api.main import app
import api.main as main
from api.services import register_selected_model


@pytest.fixture(scope="session", autouse=True)
def migrate_test_database():
    url = make_url(get_settings().database_url)
    assert url.get_backend_name() == "postgresql" and url.database.endswith(
        "_test"
    ), "Tes hanya boleh menggunakan PostgreSQL dengan nama *_test."
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")  # Aman diulang tanpa membuat tabel/data duplikat.
    yield
    engine.dispose()


@pytest.fixture
def factory(monkeypatch, tmp_path):
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
    monkeypatch.setattr(main, "SessionLocal", sessions)
    monkeypatch.setattr(get_settings(), "storage_path", tmp_path)
    monkeypatch.setattr(get_settings(), "mail_backend", "disabled")
    with sessions() as db:
        register_selected_model(db)
        db.commit()
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
        json={
            "name": "Manager Uji",
            "email": email,
            "password": "FoodSave-Test-2026!",
            "restaurant_name": name,
        },
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
