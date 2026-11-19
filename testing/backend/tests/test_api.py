"""Tes fitur API per halaman, dikelompokkan menurut jenis data yang dipakai."""

import csv
import io
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from sqlalchemy import select, text

from app.core.security import token_digest
from app.main import app
from app.models import (
    InferenceLog,
    ModelVersion,
    Notification,
    PredictionResult,
    ReportExport,
    UserSession,
)
from tests.conftest import PASSWORD, count, register


def D(value):
    """Angka JSON (float) menjadi Decimal tanpa galat biner."""
    return Decimal(str(value))


# --- Kesehatan dan akun --------------------------------------------------------
def test_health_ready_reports_database_storage_and_model(client, prepared):
    assert client.get("/health/live").json()["status"] == "alive"
    ready = client.get("/health/ready")
    assert ready.status_code == 200, ready.text
    body = ready.json()
    assert body["database"] == "connected" and body["storage"] == "local"
    assert body["model"] == prepared["summary"]["version_key"]


def test_authentication_hash_session_and_logout(client, factory):
    user = register(client)
    assert "password_hash" not in user
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["role"] == "owner"
    token = client.cookies.get("foodsave_session")
    with factory() as db:
        session = db.scalar(select(UserSession).where(UserSession.token_hash == token_digest(token)))
        assert session is not None and token not in session.token_hash
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("foodsave_session", token)
    assert client.get("/api/v1/auth/me").status_code == 401
    bad = client.post("/api/v1/auth/login", json={"email": "owner@example.test", "password": "salah-sekali-123"})
    assert bad.status_code == 401
    ok = client.post("/api/v1/auth/login", json={"email": "owner@example.test", "password": PASSWORD})
    assert ok.status_code == 200


def test_initial_thresholds_follow_active_model_defaults(client, owner, factory):
    settings = client.get("/api/v1/settings").json()
    with factory() as db:
        active = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    assert D(settings["safe_max_kg"]) == active.default_safe_max_kg
    assert D(settings["warning_max_kg"]) == active.default_warning_max_kg
    bad = dict(settings, safe_max_kg="50", warning_max_kg="40")
    bad = {k: bad[k] for k in ["ingredient_cost_per_kg", "safe_max_kg", "warning_max_kg",
                               "max_portions", "reduction_target_percent"]}
    assert client.put("/api/v1/settings", json=bad).status_code == 422


# --- Input data harian (data operasional + prediksi realtime) -------------------
def test_daily_duplicate_and_versioned_correction(client, owner, operation_payload):
    created = client.post("/api/v1/daily-operations", json=operation_payload)
    assert created.status_code == 201
    assert client.post("/api/v1/daily-operations", json=operation_payload).status_code == 409
    op = created.json()
    update = dict(operation_payload, actual_waste_kg=31.5, expected_version=1,
                  correction_reason="Aktual dicatat")
    updated = client.put(f"/api/v1/daily-operations/{op['id']}", json=update)
    assert updated.status_code == 200 and updated.json()["version"] == 2
    stale = client.put(f"/api/v1/daily-operations/{op['id']}", json=update)
    assert stale.status_code == 409
    history = client.get(f"/api/v1/daily-operations/{op['id']}/corrections").json()
    assert len(history) == 1 and history[0]["reason"] == "Aktual dicatat"


def test_realtime_prediction_is_saved_with_version_interval_and_log(
    client, owner, operation_payload, factory, prepared
):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    result = client.post(f"/api/v1/daily-operations/{op['id']}/predict")
    assert result.status_code == 201, result.text
    body = result.json()
    lower, value, upper = (D(body[k]) for k in
                           ["interval_lower_kg", "predicted_waste_kg", "interval_upper_kg"])
    radius = Decimal(str(prepared["summary"]["interval_radius_kg"]))
    assert lower <= value <= upper and abs((upper - value) - radius) < Decimal("0.001")
    assert "actual_waste_kg" in body["input_snapshot"]  # snapshot lengkap disimpan
    with factory() as db:
        logs = db.scalars(select(InferenceLog).where(InferenceLog.source == "daily")).all()
        version = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    assert len(logs) == 1 and logs[0].success and logs[0].row_count == 1
    assert body["model_version_id"] == str(version.id)


def test_actual_value_never_changes_the_prediction(client, owner, operation_payload):
    first = client.post("/api/v1/predictions/preview", json={
        k: operation_payload[k] for k in ["operation_date", "meals_prepared", "kitchen_staff",
                                          "staff_experience", "special_event", "temperature_c",
                                          "humidity_percent"]}).json()
    op = client.post("/api/v1/daily-operations",
                     json=dict(operation_payload, actual_waste_kg=999)).json()
    saved = client.post(f"/api/v1/daily-operations/{op['id']}/predict").json()
    assert D(first["predicted_waste_kg"]) == D(saved["predicted_waste_kg"])


def test_preview_does_not_save_prediction_and_flags_unusual_input(client, owner, factory):
    payload = {"operation_date": "2026-11-12", "meals_prepared": 2000, "kitchen_staff": 10,
               "staff_experience": "beginner", "special_event": True, "temperature_c": 25,
               "humidity_percent": 60}
    response = client.post("/api/v1/predictions/preview", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["outside_training_range"] is True and "meals_prepared" in body["outside_fields"]
    assert count(factory, "prediction.prediction_results") == 0
    assert count(factory, "prediction.inference_logs") == 1


def test_high_risk_prediction_creates_notification(client, owner, operation_payload, factory):
    client.put("/api/v1/settings", json={
        "ingredient_cost_per_kg": "50000", "safe_max_kg": "0.1", "warning_max_kg": "0.2",
        "max_portions": 5000, "reduction_target_percent": "10"})
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    result = client.post(f"/api/v1/daily-operations/{op['id']}/predict").json()
    assert result["risk_level"] == "high"
    assert D(result["estimated_waste_cost"]) == (
        D(result["predicted_waste_kg"]) * 50000).quantize(Decimal(".01"))
    notes = client.get("/api/v1/notifications").json()
    assert len(notes) == 1 and notes[0]["prediction_result_id"] == result["id"]
    read = client.patch(f"/api/v1/notifications/{notes[0]['id']}/read")
    assert read.json()["read_at"] is not None


def test_tenant_isolation_and_staff_role(client, owner, operation_payload):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    staff = client.post("/api/v1/auth/users", json={
        "name": "Staf", "email": "staf@example.test", "password": PASSWORD, "role": "staff"})
    assert staff.status_code == 201
    with TestClient(app) as other:
        register(other, "lain@example.test", "Restoran Lain")
        assert other.get(f"/api/v1/daily-operations/{op['id']}").status_code == 404
        assert other.post(f"/api/v1/daily-operations/{op['id']}/predict").status_code == 404
    with TestClient(app) as staff_client:
        staff_client.post("/api/v1/auth/login",
                          json={"email": "staf@example.test", "password": PASSWORD})
        assert staff_client.get(f"/api/v1/daily-operations/{op['id']}").status_code == 200
        assert staff_client.post(f"/api/v1/daily-operations/{op['id']}/predict").status_code == 403


def test_capacity_limit_is_enforced(client, owner, operation_payload):
    payload = dict(operation_payload, meals_prepared=6000)
    assert client.post("/api/v1/daily-operations", json=payload).status_code == 422


# --- Prediksi 7 hari -------------------------------------------------------------
def week(start_day=16):
    return [
        {"operation_date": f"2026-11-{start_day + i:02d}", "meals_prepared": 300 + 20 * i,
         "kitchen_staff": 10, "staff_experience": "intermediate", "special_event": i == 5,
         "temperature_c": 27, "humidity_percent": 70}
        for i in range(7)
    ]


def test_weekly_plan_predicts_seven_days_in_one_model_call(client, owner, factory):
    response = client.post("/api/v1/weekly-predictions",
                           json={"title": "Minggu uji", "starts_on": "2026-11-16", "days": week()})
    assert response.status_code == 201, response.text
    plan = response.json()
    assert len(plan["days"]) == 7 and all(d["prediction"] for d in plan["days"])
    with factory() as db:
        logs = db.scalars(select(InferenceLog).where(InferenceLog.source == "weekly")).all()
    assert [log.row_count for log in logs] == [7]
    day = plan["days"][2]
    changed = dict(day["input_snapshot"], meals_prepared=500, expected_version=day["version"],
                   correction_reason="Ada pesanan katering")
    updated = client.put(f"/api/v1/weekly-predictions/{plan['id']}/days/{day['id']}", json=changed)
    assert updated.status_code == 200
    assert updated.json()["days"][2]["input_snapshot"]["meals_prepared"] == 500
    assert len(client.get(f"/api/v1/weekly-predictions/{plan['id']}/revisions").json()) == 1


def test_weekly_requires_consecutive_dates(client, owner):
    days = week()
    days[3]["operation_date"] = "2026-11-30"
    response = client.post("/api/v1/weekly-predictions",
                           json={"title": "Salah", "starts_on": "2026-11-16", "days": days})
    assert response.status_code == 422


# --- Simulasi porsi --------------------------------------------------------------
def test_scenario_options_create_and_idempotent_apply(client, owner, operation_payload, factory):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    options = client.post("/api/v1/portion-scenarios/options",
                          json={"daily_operation_id": op["id"]})
    assert options.status_code == 200, options.text
    body = options.json()
    assert [o["reduction_percent"] for o in body["options"]] == [0, 5, 10, 15]
    assert [o["simulated_portions"] for o in body["options"]] == [400, 380, 360, 340]
    assert D(body["options"][0]["savings_kg"]) == 0
    scenario = client.post("/api/v1/portion-scenarios", json={
        "daily_operation_id": op["id"], "reduction_percent": 10,
        "application_date": "2026-11-11", "status": "saved"}).json()
    assert scenario["simulated_portions"] == 360
    applied = client.post(f"/api/v1/portion-scenarios/{scenario['id']}/apply",
                          json={"expected_operation_version": 1})
    assert applied.status_code == 200 and applied.json()["operation"]["meals_prepared"] == 360
    again = client.post(f"/api/v1/portion-scenarios/{scenario['id']}/apply",
                        json={"expected_operation_version": 2})
    assert again.json()["already_applied"] is True
    with factory() as db:
        rows = [log.row_count for log in db.scalars(
            select(InferenceLog).where(InferenceLog.source == "scenario")
            .order_by(InferenceLog.created_at))]
    assert rows == [5, 2, 1]


def test_stale_scenario_cannot_overwrite_new_plan(client, owner, operation_payload):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    scenario = client.post("/api/v1/portion-scenarios", json={
        "daily_operation_id": op["id"], "reduction_percent": 5,
        "application_date": "2026-11-11"}).json()
    client.put(f"/api/v1/daily-operations/{op['id']}", json=dict(
        operation_payload, meals_prepared=450, expected_version=1, correction_reason="Ubah"))
    stale = client.post(f"/api/v1/portion-scenarios/{scenario['id']}/apply",
                        json={"expected_operation_version": 2})
    assert stale.status_code == 409


# --- Unggah CSV/Excel (tanpa model) ---------------------------------------------
def test_csv_import_validates_applies_and_does_not_call_model(client, owner, factory):
    rows = [
        "date,meals_served,kitchen_staff,temperature_C,humidity_percent,day_of_week,special_event,"
        "past_waste_kg,staff_experience,waste_category,food_waste_kg",
        "2026-10-01,300,10,27,70,3,0,20,Intermediate,meat,30.5",
        "2026-10-02,320,11,28,71,4,0,21,ahli,dairy,",
        "2026-10-03,abc,11,28,71,5,0,21,expert,dairy,10",
    ]
    file = io.BytesIO("\n".join(rows).encode())
    response = client.post("/api/v1/imports?apply=true",
                           files={"file": ("harian.csv", file, "text/csv")})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["valid_rows"] == 2 and body["invalid_rows"] == 1 and body["applied_rows"] == 2
    assert client.get(f"/api/v1/imports/{body['id']}/file").content.startswith(b"date,")
    assert count(factory, "operational.daily_operations") == 2
    assert count(factory, "prediction.inference_logs") == 0


def test_excel_import_dry_run(client, owner, factory):
    book = Workbook()
    sheet = book.active
    sheet.append(["operation_date", "meals_prepared", "kitchen_staff", "staff_experience",
                  "special_event", "temperature_c", "humidity_percent"])
    sheet.append(["2026-09-01", 280, 9, "beginner", False, 26, 65])
    buffer = io.BytesIO()
    book.save(buffer)
    response = client.post("/api/v1/imports", files={"file": (
        "harian.xlsx", buffer.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 201 and response.json()["status"] == "validated"
    assert count(factory, "operational.daily_operations") == 0


# --- Dashboard (hanya membaca) -----------------------------------------------------
def test_dashboard_flags_stale_prediction_and_trend_mae(client, owner, operation_payload):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    view = client.get("/api/v1/dashboard", params={"on": "2026-11-11"}).json()
    assert view["prediction"] is None and view["prediction_is_stale"] is True
    pred = client.post(f"/api/v1/daily-operations/{op['id']}/predict").json()
    view = client.get("/api/v1/dashboard", params={"on": "2026-11-11"}).json()
    assert view["prediction_is_stale"] is False and view["model"]["version_key"]
    client.put(f"/api/v1/daily-operations/{op['id']}", json=dict(
        operation_payload, actual_waste_kg=40, expected_version=1, correction_reason="Aktual"))
    view = client.get("/api/v1/dashboard", params={"on": "2026-11-11"}).json()
    assert view["prediction_is_stale"] is True  # input berubah setelah prediksi terakhir
    trend = client.get("/api/v1/dashboard/trend", params={"end": "2026-11-11", "days": 7}).json()
    expected = abs(Decimal("40") - D(pred["predicted_waste_kg"]))
    assert trend["paired_days"] == 1 and D(trend["mae_kg"]) == expected.quantize(Decimal(".0001"))


# --- Laporan ---------------------------------------------------------------------
def test_summary_uses_actuals_and_stored_predictions(client, owner, operation_payload):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    client.post(f"/api/v1/daily-operations/{op['id']}/predict")
    client.post("/api/v1/daily-operations", json=dict(operation_payload,
                                                      operation_date="2026-11-12"))
    client.put(f"/api/v1/daily-operations/{op['id']}", json=dict(
        operation_payload, actual_waste_kg=30, expected_version=1, correction_reason="Aktual"))
    summary = client.get("/api/v1/reports/summary",
                         params={"starts_on": "2026-11-01", "ends_on": "2026-11-30"}).json()
    assert summary["operation_count"] == 2 and summary["actual_recorded_count"] == 1
    assert summary["actual_missing_count"] == 1 and summary["prediction_pairs"] == 1


@pytest.mark.parametrize("fmt", ["pdf", "xlsx"])
def test_report_export_is_a_real_file(client, owner, operation_payload, fmt):
    op = client.post("/api/v1/daily-operations",
                     json=dict(operation_payload, manager_notes="=SUM(A1:A2)")).json()
    client.post(f"/api/v1/daily-operations/{op['id']}/predict")
    export = client.post("/api/v1/report-exports", json={
        "starts_on": "2026-11-01", "ends_on": "2026-11-30", "file_format": fmt}).json()
    assert export["generation_status"] == "ready"
    content = client.get(f"/api/v1/report-exports/{export['id']}/file").content
    if fmt == "pdf":
        assert content.startswith(b"%PDF-")
    else:
        sheet = load_workbook(io.BytesIO(content)).active
        header = [c.value for c in sheet[1]]
        assert "Prediksi kg" in header and sheet.cell(2, header.index("Prediksi kg") + 1).value
        assert sheet.cell(2, len(header)).value == "'=SUM(A1:A2)"


# --- Insight operasional dan data statis model -----------------------------------
def test_operational_insight_groups(client, owner, operation_payload):
    client.post("/api/v1/daily-operations", json=dict(operation_payload, actual_waste_kg=35))
    view = client.get("/api/v1/insights/operational",
                      params={"starts_on": "2026-11-01", "ends_on": "2026-11-30"}).json()
    assert sum(g["operation_count"] for g in view["staff_load"]) == 1
    assert view["categories"][0]["category"] == "vegetables"


def test_static_model_analysis_endpoints(client, owner, prepared):
    active = client.get("/api/v1/model/active").json()
    assert active["version_key"] == prepared["summary"]["version_key"]
    assert active["loaded_in_memory"] is True and "model_path" not in active
    scopes = {e["scope"] for e in client.get("/api/v1/model/evaluations").json()["items"]}
    assert scopes == {"cv_dev", "test", "baseline_test"}
    trials = client.get("/api/v1/model/tuning").json()["trials"]
    assert len(trials) == 2 and sum(t["is_best"] for t in trials) == 1
    factors = client.get("/api/v1/model/feature-importances").json()["items"]
    assert factors[0]["rank"] == 1 and len(factors) == 14
    curve = client.get("/api/v1/model/sensitivity",
                       params={"staff_experience": "expert", "special_event": True}).json()
    assert len(curve["points"]) == 31 and curve["points"][0]["meals_prepared"] == 50
    test_rows = client.get("/api/v1/model/evaluation-predictions").json()["items"]
    assert len(test_rows) > 100 and all(r["source"] == "seed" for r in test_rows)
    reports = client.get("/api/v1/model/evaluation-reports").json()["items"]
    pdf = next(r for r in reports if r["file_format"] == "pdf")
    file = client.get(f"/api/v1/model/evaluation-reports/{pdf['id']}/file")
    assert file.status_code == 200 and file.content.startswith(b"%PDF-")


def test_model_reload_is_owner_only(client, owner):
    assert client.post("/api/v1/model/reload").status_code == 200
    client.post("/api/v1/auth/users", json={
        "name": "Manager", "email": "mgr@example.test", "password": PASSWORD, "role": "manager"})
    with TestClient(app) as manager:
        manager.post("/api/v1/auth/login", json={"email": "mgr@example.test", "password": PASSWORD})
        assert manager.post("/api/v1/model/reload").status_code == 403


# --- Aliran balik data aktual ke HDFS --------------------------------------------
def test_training_export_writes_raw_csv_and_is_incremental(
    client, owner, operation_payload, prepared
):
    client.post("/api/v1/daily-operations", json=dict(operation_payload, actual_waste_kg=33.25))
    client.post("/api/v1/daily-operations", json=dict(operation_payload,
                                                      operation_date="2026-11-12"))
    first = client.post("/api/v1/training-exports")
    assert first.status_code == 201, first.text
    assert first.json()["status"] == "completed" and first.json()["row_count"] == 1
    files = [e for e in prepared["storage"].list("/foodsave/raw/actuals")]
    content = prepared["storage"].read_bytes(files[-1].path).decode()
    row = next(csv.DictReader(io.StringIO(content)))
    assert row["date"] == "2026-11-11" and row["meals_served"] == "400"
    assert row["food_waste_kg"] == "33.25" and row["source"] == "actuals"
    second = client.post("/api/v1/training-exports").json()
    assert second["status"] == "empty" and second["row_count"] == 0
    prepared["storage"].delete(files[-1].path)  # jangan memengaruhi tes pelatihan ulang


# --- Batasan database -------------------------------------------------------------
def test_database_allows_only_one_active_model(factory):
    with factory() as db:
        other = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
        with pytest.raises(Exception):
            db.execute(text(
                "INSERT INTO model_analysis.model_versions (id, version_key, name, params,"
                " storage_dir, model_path, preprocessing_path, manifest_path, model_sha256,"
                " preprocessing_sha256, input_features, feature_columns, training_ranges,"
                " interval_radius_kg, default_safe_max_kg, default_warning_max_kg, trained_rows,"
                " trained_from, trained_to, sklearn_version, metrics, is_active)"
                " SELECT gen_random_uuid(), 'tiruan', name, params, storage_dir, model_path,"
                " preprocessing_path, manifest_path, model_sha256, preprocessing_sha256,"
                " input_features, feature_columns, training_ranges, interval_radius_kg,"
                " default_safe_max_kg, default_warning_max_kg, trained_rows, trained_from,"
                " trained_to, sklearn_version, metrics, true FROM model_analysis.model_versions"
                " WHERE id = :id"), {"id": other.id})
            db.flush()


def test_cross_restaurant_prediction_link_is_rejected(client, owner, operation_payload, factory):
    op = client.post("/api/v1/daily-operations", json=operation_payload).json()
    result = client.post(f"/api/v1/daily-operations/{op['id']}/predict").json()
    other = register(TestClient(app), "x@example.test", "Restoran X")
    with factory() as db:
        with pytest.raises(Exception):
            row = db.get(PredictionResult, UUID(result["id"]))
            db.add(Notification(restaurant_id=UUID(other["restaurant_id"]),
                                user_id=UUID(other["id"]), prediction_result_id=row.id,
                                title="x", message="x"))
            db.flush()


def test_ready_report_without_file_is_rejected(client, owner, factory):
    with factory() as db:
        with pytest.raises(Exception):
            db.add(ReportExport(restaurant_id=UUID(owner["restaurant_id"]),
                                created_by=UUID(owner["id"]), starts_on="2026-11-01",
                                ends_on="2026-11-02", period_type="custom", file_format="pdf",
                                generation_status="ready"))
            db.flush()


def test_cross_origin_write_is_blocked(client, owner, operation_payload):
    response = client.post("/api/v1/daily-operations", json=operation_payload,
                           headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
