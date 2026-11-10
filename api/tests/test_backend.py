from datetime import date, timedelta
from decimal import Decimal
import io
from uuid import UUID
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from api.auth import password_hash, verify_password
from api.main import HEAD_REVISION, app
from api.models import (
    DataCorrection,
    DataImport,
    DailyOperation,
    ModelVersion,
    PlanRevision,
    PredictionDay,
    PredictionResult,
    RestaurantSettings,
    User,
    UserSession,
    WeeklyPrediction,
)
from api.tests.conftest import register


def create(client, payload):
    response = client.post("/api/v1/daily-operations", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_health_and_database_revision(client, factory):
    assert client.get("/health/live").json()["status"] == "alive"
    response = client.get("/health/ready")
    assert response.status_code == 200, response.text
    assert response.json()["database"] == "connected"
    with factory() as db:
        assert db.scalar(text("SELECT version_num FROM alembic_version")) == HEAD_REVISION
        assert (
            db.scalar(
                select(func.count())
                .select_from(ModelVersion)
                .where(ModelVersion.is_active.is_(True))
            )
            == 1
        )
        assert db.scalar(select(func.count()).select_from(ModelVersion)) >= 1


def test_authentication_hash_session_and_logout(client, factory):
    assert client.get("/api/v1/auth/me").status_code == 401
    owner = register(client)
    assert "password_hash" not in owner
    with factory() as db:
        user = db.get(User, UUID(owner["id"]))
        assert user.password_hash != "FoodSave-Test-2026!"
        assert verify_password("FoodSave-Test-2026!", user.password_hash)
        session = db.scalar(select(UserSession))
        assert session.token_hash not in client.cookies.values()
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": "owner@example.test", "password": "wrong-password"}
        ).status_code
        == 401
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.test", "password": "FoodSave-Test-2026!"},
    )
    assert login.status_code == 200
    assert (
        "httponly" in login.headers["set-cookie"].lower()
        and "samesite=lax" in login.headers["set-cookie"].lower()
    )


def test_settings_validation_and_restaurant_update(client, owner):
    assert (
        client.put("/api/v1/restaurant", json={"name": "Restoran FoodSave"}).json()["name"]
        == "Restoran FoodSave"
    )
    settings = client.get("/api/v1/settings").json()
    settings.pop("restaurant_id")
    settings.pop("updated_at")
    settings.update(ingredient_cost_per_kg=50000, safe_max_kg=20, warning_max_kg=40)
    assert client.put("/api/v1/settings", json=settings).status_code == 200
    settings["warning_max_kg"] = 10
    assert client.put("/api/v1/settings", json=settings).status_code == 422


def test_daily_persistence_duplicate_and_versioned_correction(
    client, owner, operation_payload, factory
):
    row = create(client, operation_payload)
    assert row["version"] == 1
    assert client.post("/api/v1/daily-operations", json=operation_payload).status_code == 409
    changed = {
        **operation_payload,
        "actual_waste_kg": 18.5,
        "expected_version": 1,
        "correction_reason": "Penimbangan selesai.",
    }
    updated = client.put(f"/api/v1/daily-operations/{row['id']}", json=changed)
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert client.put(f"/api/v1/daily-operations/{row['id']}", json=changed).status_code == 409
    with factory() as db:
        stored = db.get(DailyOperation, UUID(row["id"]))
        assert stored.actual_waste_kg == Decimal("18.5000")
        correction = db.scalar(select(DataCorrection))
        assert correction.previous_values["actual_waste_kg"] is None
        assert correction.new_values["actual_waste_kg"] == "18.5"
    invalid = {**operation_payload, "operation_date": "2026-11-12", "kitchen_staff": 0}
    assert client.post("/api/v1/daily-operations", json=invalid).status_code == 422


def test_prediction_persistence_version_and_input_snapshot(
    client, owner, operation_payload, factory
):
    row = create(client, operation_payload)
    response = client.post(f"/api/v1/daily-operations/{row['id']}/predict")
    assert response.status_code == 201, response.text
    pred = response.json()
    assert 0 <= pred["interval_lower_kg"] <= pred["predicted_waste_kg"] <= pred["interval_upper_kg"]
    assert pred["input_snapshot"]["meals_prepared"] == 400
    assert pred["model_version_id"] and pred["operation_version"] == 1
    assert pred["portions_per_staff"] == 33.3333
    with factory() as db:
        saved = db.get(PredictionResult, UUID(pred["id"]))
        assert saved.daily_operation_id == UUID(row["id"])
        assert db.get(ModelVersion, saved.model_version_id).name == "RandomForest"
    changed = {
        **operation_payload,
        "meals_prepared": 350,
        "expected_version": 1,
        "correction_reason": "Rencana diperbarui.",
    }
    assert client.put(f"/api/v1/daily-operations/{row['id']}", json=changed).status_code == 200
    assert (
        client.get(f"/api/v1/predictions/{pred['id']}").json()["input_snapshot"]["meals_prepared"]
        == 400
    )
    assert client.get("/api/v1/overview?on=2026-11-11").json()["prediction"] is None


def test_tenant_isolation_and_staff_role(client, owner, operation_payload, factory):
    row = create(client, operation_payload)
    with TestClient(app) as other:
        register(other, "other@example.test", "Restoran Lain")
        assert other.get(f"/api/v1/daily-operations/{row['id']}").status_code == 404
        assert other.post(f"/api/v1/daily-operations/{row['id']}/predict").status_code == 404
        assert other.get("/api/v1/daily-operations").json()["total"] == 0
    created = client.post(
        "/api/v1/auth/users",
        json={
            "name": "Staf Uji",
            "email": "staff@example.test",
            "password": "FoodSave-Test-2026!",
            "role": "staff",
        },
    )
    assert created.status_code == 201, created.text
    with TestClient(app) as staff:
        assert (
            staff.post(
                "/api/v1/auth/login",
                json={"email": "staff@example.test", "password": "FoodSave-Test-2026!"},
            ).status_code
            == 200
        )
        assert staff.get("/api/v1/daily-operations").status_code == 200
        assert (
            staff.post(
                "/api/v1/daily-operations",
                json={**operation_payload, "operation_date": "2026-11-12"},
            ).status_code
            == 403
        )


def test_scenario_apply_is_atomic_and_idempotent(client, owner, operation_payload, factory):
    row = create(client, operation_payload)
    response = client.post(
        "/api/v1/portion-scenarios",
        json={
            "daily_operation_id": row["id"],
            "reduction_percent": 10,
            "application_date": "2026-11-11",
            "status": "saved",
        },
    )
    assert response.status_code == 201, response.text
    scenario = response.json()
    assert scenario["simulated_portions"] == 360 and scenario["shortage_risk"] == "unknown"
    url = f"/api/v1/portion-scenarios/{scenario['id']}/apply"
    applied = client.post(url, json={"expected_operation_version": 1})
    assert applied.status_code == 200, applied.text
    assert applied.json()["operation"]["meals_prepared"] == 360
    assert applied.json()["operation"]["version"] == 2
    assert (
        client.post(url, json={"expected_operation_version": 1}).json()["already_applied"] is True
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DataCorrection)) == 1
        assert db.scalar(select(func.count()).select_from(PredictionResult)) == 1


def test_stale_scenario_cannot_overwrite_new_plan(client, owner, operation_payload):
    row = create(client, operation_payload)
    scenario = client.post(
        "/api/v1/portion-scenarios",
        json={
            "daily_operation_id": row["id"],
            "reduction_percent": 5,
            "application_date": "2026-11-11",
        },
    ).json()
    client.put(
        f"/api/v1/daily-operations/{row['id']}",
        json={
            **operation_payload,
            "meals_prepared": 450,
            "expected_version": 1,
            "correction_reason": "Ada tambahan pelanggan.",
        },
    )
    assert (
        client.post(
            f"/api/v1/portion-scenarios/{scenario['id']}/apply",
            json={"expected_operation_version": 2},
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/daily-operations/{row['id']}").json()["meals_prepared"] == 450


def test_weekly_seven_days_and_plan_revision(client, owner, operation_payload, factory):
    start = date(2026, 11, 11)
    days = [
        {**operation_payload, "operation_date": str(start + timedelta(days=i))} for i in range(7)
    ]
    response = client.post(
        "/api/v1/weekly-predictions",
        json={"title": "Rencana satu minggu", "starts_on": str(start), "days": days},
    )
    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["days"]) == 7 and all(d["prediction"] for d in plan["days"])
    day = plan["days"][0]
    update = {
        **days[0],
        "meals_prepared": 375,
        "expected_version": 1,
        "correction_reason": "Perkiraan permintaan terbaru.",
    }
    response = client.put(f"/api/v1/weekly-predictions/{plan['id']}/days/{day['id']}", json=update)
    assert response.status_code == 200, response.text
    assert response.json()["days"][0]["version"] == 2
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PlanRevision)) == 1
        assert db.scalar(select(func.count()).select_from(PredictionResult)) == 8
    invalid = {**days[-1], "operation_date": days[0]["operation_date"]}
    assert (
        client.post(
            "/api/v1/weekly-predictions",
            json={
                "title": "Tanggal tidak valid",
                "starts_on": str(start),
                "days": days[:-1] + [invalid],
            },
        ).status_code
        == 422
    )


def test_csv_import_validation_apply_and_file_download(client, owner, factory):
    csv = "operation_date,meals_prepared,kitchen_staff,staff_experience,temperature_c,humidity_percent\n2026-11-11,400,12,Menengah,28,65\n2026-11-12,400,0,Pemula,28,65\n"
    response = client.post(
        "/api/v1/imports?apply=true", files={"file": ("uji.csv", csv, "text/csv")}
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert (result["valid_rows"], result["invalid_rows"], result["applied_rows"]) == (1, 1, 1)
    assert client.get(f"/api/v1/imports/{result['id']}/file").text == csv
    with factory() as db:
        operation = db.scalar(select(DailyOperation))
        assert operation.source == "import" and str(operation.import_id) == result["id"]
    assert (
        client.post(
            "/api/v1/imports", files={"file": ("bad.exe", b"bad", "application/octet-stream")}
        ).status_code
        == 415
    )


def test_excel_import_and_dry_run(client, owner, factory):
    from openpyxl import Workbook

    stream = io.BytesIO()
    book = Workbook()
    sheet = book.active
    sheet.append(
        [
            "operation_date",
            "meals_prepared",
            "kitchen_staff",
            "staff_experience",
            "temperature_c",
            "humidity_percent",
        ]
    )
    sheet.append(["2026-11-11", 300, 10, "Ahli", 28, 60])
    book.save(stream)
    response = client.post(
        "/api/v1/imports",
        files={
            "file": (
                "uji.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["valid_rows"] == 1 and response.json()["applied_rows"] == 0
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DailyOperation)) == 0


def test_summary_uses_actuals_without_inventing_missing_values(client, owner, operation_payload):
    create(client, {**operation_payload, "actual_waste_kg": 12.5})
    create(client, {**operation_payload, "operation_date": "2026-11-12"})
    result = client.get("/api/v1/reports/summary?starts_on=2026-11-01&ends_on=2026-11-30").json()
    assert result["operation_count"] == 2 and result["actual_missing_count"] == 1
    assert result["total_actual_waste_kg"] == 12.5 and result["average_actual_waste_kg"] == 12.5
    export = client.post(
        "/api/v1/report-exports",
        json={"starts_on": "2026-11-01", "ends_on": "2026-11-30", "file_format": "xlsx"},
    )
    assert export.status_code == 201, export.text
    assert export.json()["generation_status"] == "ready"
    download = client.get(f"/api/v1/report-exports/{export.json()['id']}/file")
    assert download.status_code == 200 and download.content.startswith(b"PK")
    from openpyxl import load_workbook

    book = load_workbook(io.BytesIO(download.content), data_only=False)
    assert book["Ringkasan"]["B6"].value == 12.5
    assert (
        book["Data operasional"]["G2"].value is None
        and book["Data operasional"]["G3"].value == 12.5
    )
    book.close()
    assert client.get(f"/api/v1/report-exports/{export.json()['id']}").json()["downloaded_at"]


def test_tasks_notifications_and_insight_status(client, owner, operation_payload):
    task = client.post(
        "/api/v1/daily-tasks", json={"task_date": "2026-11-11", "title": "Timbang limbah aktual"}
    ).json()
    assert client.patch(f"/api/v1/daily-tasks/{task['id']}", json={"completed": True}).json()[
        "completed_at"
    ]
    insight = client.post(
        "/api/v1/insights",
        json={
            "title": "Periksa jumlah porsi",
            "suggested_action": "Tinjau rencana berdasarkan kebutuhan pelanggan.",
        },
    ).json()
    assert insight["created_by"] == owner["id"]
    assert (
        client.patch(f"/api/v1/insights/{insight['id']}", json={"status": "reviewed"}).json()[
            "status"
        ]
        == "reviewed"
    )
    settings = client.get("/api/v1/settings").json()
    settings.pop("restaurant_id")
    settings.pop("updated_at")
    settings.update(safe_max_kg=0, warning_max_kg=0.01)
    assert client.put("/api/v1/settings", json=settings).status_code == 200
    row = create(client, operation_payload)
    assert (
        client.post(f"/api/v1/daily-operations/{row['id']}/predict").json()["risk_level"] == "high"
    )
    notifications = client.get("/api/v1/notifications").json()
    assert len(notifications) == 1
    assert client.patch(f"/api/v1/notifications/{notifications[0]['id']}/read").json()["read_at"]


def test_database_constraint_and_cross_origin_protection(client, owner, operation_payload, factory):
    assert (
        client.post(
            "/api/v1/daily-operations",
            json=operation_payload,
            headers={"Origin": "https://attacker.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/daily-operations",
            json=operation_payload,
            headers={"Origin": "http://localhost:3000"},
        ).status_code
        == 201
    )
    with factory() as db:
        try:
            with db.begin_nested():
                db.execute(
                    update(RestaurantSettings)
                    .where(RestaurantSettings.restaurant_id == UUID(owner["restaurant_id"]))
                    .values(safe_max_kg=50, warning_max_kg=10)
                )
        except IntegrityError:
            pass
        else:
            raise AssertionError("Database harus menolak pengaturan yang bertabrakan/tidak valid.")


def test_old_session_is_revoked(client, owner):
    sessions = client.get("/api/v1/auth/sessions").json()
    assert len(sessions) == 1
    assert client.delete("/api/v1/auth/sessions/" + sessions[0]["id"]).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"meals_prepared": -1},
        {"kitchen_staff": 0},
        {"humidity_percent": 101},
        {"temperature_c": 101},
        {"previous_waste_kg": -1},
        {"actual_waste_kg": -1},
        {"staff_experience": "unknown"},
        {"special_event": False, "event_type": "Pernikahan"},
    ],
)
def test_invalid_input_does_not_create_rows(client, owner, operation_payload, factory, changes):
    assert (
        client.post("/api/v1/daily-operations", json={**operation_payload, **changes}).status_code
        == 422
    )
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DailyOperation)) == 0


def test_capacity_limit_is_enforced(client, owner, operation_payload):
    assert (
        client.post(
            "/api/v1/daily-operations", json={**operation_payload, "meals_prepared": 5001}
        ).status_code
        == 422
    )


def test_weekly_failure_rolls_back_all_days(client, owner, operation_payload, factory, monkeypatch):
    import api.routers.weekly as weekly

    real_predict = weekly.calculate_prediction

    def fail_third(db, user, snapshot, **kwargs):
        if snapshot["operation_date"] == "2026-11-13":
            raise HTTPException(503, "Kegagalan inferensi uji.")
        return real_predict(db, user, snapshot, **kwargs)

    monkeypatch.setattr(weekly, "calculate_prediction", fail_third)
    start = date(2026, 11, 11)
    days = [
        {**operation_payload, "operation_date": str(start + timedelta(days=i))} for i in range(7)
    ]
    response = client.post(
        "/api/v1/weekly-predictions",
        json={"title": "Uji transaksi gagal", "starts_on": str(start), "days": days},
    )
    assert response.status_code == 503, response.text
    with factory() as db:
        for model in [WeeklyPrediction, PredictionDay, PredictionResult]:
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_scenario_failure_rolls_back_plan_audit_and_status(
    client, owner, operation_payload, factory, monkeypatch
):
    import api.routers.what_if as what_if

    row = create(client, operation_payload)
    scenario = client.post(
        "/api/v1/portion-scenarios",
        json={
            "daily_operation_id": row["id"],
            "reduction_percent": 10,
            "application_date": "2026-11-11",
            "status": "saved",
        },
    ).json()

    def fail(*args, **kwargs):
        raise HTTPException(503, "Kegagalan inferensi uji.")

    monkeypatch.setattr(what_if, "calculate_prediction", fail)
    assert (
        client.post(
            f"/api/v1/portion-scenarios/{scenario['id']}/apply",
            json={"expected_operation_version": 1},
        ).status_code
        == 503
    )
    current = client.get(f"/api/v1/daily-operations/{row['id']}").json()
    assert current["meals_prepared"] == 400 and current["version"] == 1
    assert client.get(f"/api/v1/portion-scenarios/{scenario['id']}").json()["status"] == "saved"
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(DataCorrection)) == 0


def test_cross_restaurant_relation_is_rejected_by_postgres(
    client, owner, operation_payload, factory
):
    row = create(client, operation_payload)
    with TestClient(app) as other:
        other_owner = register(other, "different@example.test", "Restoran Kedua")
    with factory() as db:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(
                    DataCorrection(
                        restaurant_id=UUID(other_owner["restaurant_id"]),
                        daily_operation_id=UUID(row["id"]),
                        changed_by=UUID(other_owner["id"]),
                        reason="Uji FK lintas restoran",
                        previous_version=1,
                        previous_values={},
                        new_values={},
                    )
                )
                db.flush()


def test_health_returns_503_without_active_model(client, owner, operation_payload, factory):
    with factory() as db:
        for model in db.scalars(select(ModelVersion)).all():
            model.is_active = False
        db.commit()
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503
    row = create(client, operation_payload)
    assert client.post(f"/api/v1/daily-operations/{row['id']}/predict").status_code == 503
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(PredictionResult)) == 0


def test_inactive_account_cannot_reuse_session(client, owner, factory):
    with factory() as db:
        db.get(User, UUID(owner["id"])).status = "inactive"
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_pdf_export_is_a_real_downloadable_file(client, owner, operation_payload):
    create(client, {**operation_payload, "actual_waste_kg": 15})
    result = client.post(
        "/api/v1/report-exports",
        json={
            "starts_on": "2026-11-01",
            "ends_on": "2026-11-30",
            "file_format": "pdf",
            "email_recipient": "manager@example.test",
            "email_subject": "Laporan uji",
            "email_message": "Simpan untuk review.",
        },
    )
    assert result.status_code == 201, result.text
    row = result.json()
    assert row["generation_status"] == "ready" and row["email_status"] == "not_configured"
    file = client.get(f"/api/v1/report-exports/{row['id']}/file")
    assert file.status_code == 200 and file.content.startswith(b"%PDF-")


def test_health_database_failure_is_not_reported_as_ready(client, monkeypatch):
    import api.main as main
    from sqlalchemy.exc import SQLAlchemyError

    def unavailable():
        raise SQLAlchemyError("Gangguan koneksi uji.")

    monkeypatch.setattr(main, "SessionLocal", unavailable)
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 503


def test_actual_target_does_not_leak_into_model_input(client, owner, operation_payload):
    row = create(client, operation_payload)
    url = f"/api/v1/daily-operations/{row['id']}"
    first = client.post(url + "/predict").json()
    changed = {
        **operation_payload,
        "actual_waste_kg": 999,
        "previous_waste_kg": 999,
        "expected_version": 1,
        "correction_reason": "Uji pemisahan target dan fitur.",
    }
    assert client.put(url, json=changed).status_code == 200
    second = client.post(url + "/predict").json()
    assert first["predicted_waste_kg"] == second["predicted_waste_kg"]


def test_postgres_rejects_fake_ready_report_without_file(client, owner, factory):
    from api.models import ReportExport

    with factory() as db:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(
                    ReportExport(
                        restaurant_id=UUID(owner["restaurant_id"]),
                        created_by=UUID(owner["id"]),
                        starts_on=date(2026, 11, 1),
                        ends_on=date(2026, 11, 30),
                        period_type="monthly",
                        file_format="pdf",
                        generation_status="ready",
                    )
                )
                db.flush()


def test_only_one_active_model_is_allowed_by_postgres(client, factory):
    with factory() as db:
        with pytest.raises(IntegrityError):
            with db.begin_nested():
                db.add(
                    ModelVersion(
                        version_key="invalid-second-active",
                        name="RandomForest",
                        preprocessing="robust",
                        artifact_path="models/test",
                        preprocessing_path="models/test",
                        artifact_sha256="0" * 64,
                        preprocessing_sha256="0" * 64,
                        metrics={},
                        input_features=[],
                        is_active=True,
                    )
                )
                db.flush()


def test_report_failure_is_recorded_without_fake_download(client, owner, monkeypatch):
    import api.exports

    def failed(*args):
        raise OSError("Gangguan storage uji.")

    monkeypatch.setattr(api.exports, "write_export", failed)
    response = client.post(
        "/api/v1/report-exports",
        json={"starts_on": "2026-11-01", "ends_on": "2026-11-30", "file_format": "pdf"},
    )
    assert response.status_code == 201 and response.json()["generation_status"] == "failed"
    assert client.get(f"/api/v1/report-exports/{response.json()['id']}/file").status_code == 409


def test_model_catalog_contains_eight_experiments_with_one_selected(client, owner):
    models = client.get("/api/v1/models").json()
    assert len(models) == 8
    assert {(m["name"], m["preprocessing"]) for m in models} == {
        (name, method)
        for name in ["LSTM", "RandomForest", "XGBoost", "CatBoost"]
        for method in ["standard", "robust"]
    }
    active = [m for m in models if m["is_active"]]
    assert len(active) == 1 and (active[0]["name"], active[0]["preprocessing"]) == (
        "RandomForest",
        "robust",
    )
    assert all("test_MAE" in m["metrics"] for m in models)


def test_excel_user_notes_are_not_active_formulas(client, owner, operation_payload):
    from openpyxl import load_workbook

    create(client, {**operation_payload, "manager_notes": "=1+1"})
    export = client.post(
        "/api/v1/report-exports",
        json={"starts_on": "2026-11-01", "ends_on": "2026-11-30", "file_format": "xlsx"},
    ).json()
    file = client.get(f"/api/v1/report-exports/{export['id']}/file")
    book = load_workbook(io.BytesIO(file.content), data_only=False)
    assert book["Data operasional"]["H2"].data_type == "s"
    assert book["Data operasional"]["H2"].value == "'=1+1"
    book.close()


def test_insight_migration_downgrade_compiles_with_named_constraints():
    from alembic import command
    from alembic.config import Config
    from api.config import ROOT

    output = io.StringIO()
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output)
    command.downgrade(config, "0005_insight_creator:0004_email_outbox", sql=True)
    assert "DROP CONSTRAINT operational_insights_created_by_fkey" in output.getvalue()
