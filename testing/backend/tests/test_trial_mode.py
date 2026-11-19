"""Mode uji coba tanpa login (LOGIN_REQUIRED=false) untuk Prediksi 7 Hari dan Simulasi Porsi."""

import pytest

from app.core.config import get_settings
from app.core.security import COOKIE
from app.schemas import WeeklyCreate
from app.services.accounts import TRIAL_EMAIL, TRIAL_RESTAURANT
from tests.conftest import PASSWORD, count, register


@pytest.fixture
def no_login(monkeypatch):
    monkeypatch.setattr(get_settings(), "login_required", False)


def test_login_is_required_by_default(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/weekly-predictions", json={}).status_code == 401


def test_seven_day_plan_and_simulation_work_without_login(client, no_login, factory, operation_payload):
    me = client.get("/api/v1/auth/me").json()
    assert (me["email"], me["role"]) == (TRIAL_EMAIL, "owner")
    assert client.get("/api/v1/restaurant").json()["name"] == TRIAL_RESTAURANT

    plan = client.post("/api/v1/weekly-predictions", json=WeeklyCreate.model_json_schema()["examples"][0])
    assert plan.status_code == 201, plan.text
    day = plan.json()["days"][5]
    body = {**day["input_snapshot"], "meals_prepared": 450, "expected_version": day["version"],
            "correction_reason": "Pesanan katering berkurang"}
    changed = client.put(f"/api/v1/weekly-predictions/{plan.json()['id']}/days/{day['id']}", json=body)
    assert changed.status_code == 200, changed.text

    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    options = client.post("/api/v1/portion-scenarios/options", json={"daily_operation_id": op["id"]})
    assert options.status_code == 200, options.text
    scenario = client.post(
        "/api/v1/portion-scenarios",
        json={"daily_operation_id": op["id"], "reduction_percent": 10,
              "application_date": op["operation_date"], "status": "saved"},
    )
    assert scenario.status_code == 201, scenario.text
    applied = client.post(
        f"/api/v1/portion-scenarios/{scenario.json()['id']}/apply",
        json={"expected_operation_version": op["version"]},
    )
    assert applied.status_code == 200, applied.text
    assert applied.json()["operation"]["version"] == op["version"] + 1

    # Akun uji coba dibuat sekali dan dipakai ulang oleh semua permintaan.
    with factory() as db:
        from sqlalchemy import text

        assert db.scalar(text("SELECT count(*) FROM operational.users WHERE email = :e"), {"e": TRIAL_EMAIL}) == 1
    assert count(factory, "operational.restaurants") >= 1


def test_valid_session_still_wins_and_bad_cookie_falls_back(client, no_login):
    register(client)
    assert client.get("/api/v1/auth/me").json()["email"] == "owner@example.test"
    client.cookies.clear()
    client.cookies.set(COOKIE, "token-tidak-valid")
    assert client.get("/api/v1/auth/me").json()["email"] == TRIAL_EMAIL


def test_trial_account_is_reserved_and_cannot_log_in(client, no_login):
    client.get("/api/v1/auth/me")  # membuat akun uji coba
    taken = client.post(
        "/api/v1/auth/register",
        json={"name": "Orang Lain", "email": TRIAL_EMAIL, "password": PASSWORD, "restaurant_name": "Resto Lain"},
    )
    assert taken.status_code == 409
    login = client.post("/api/v1/auth/login", json={"email": TRIAL_EMAIL, "password": PASSWORD})
    assert login.status_code == 401
