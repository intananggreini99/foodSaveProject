"""Siklus penuh: data aktual -> ekspor ke HDFS -> pipeline MLflow -> versi model baru dipakai API."""

from sqlalchemy import select

from app.models import EvaluationPrediction, ModelVersion
from tests.conftest import run_pipeline


def test_actuals_feed_retraining_and_api_switches_to_new_version(
    client, owner, operation_payload, factory, prepared
):
    old_key = client.get("/api/v1/model/active").json()["version_key"]
    for day, actual in [("2026-11-09", 28.5), ("2026-11-10", 41.0), ("2026-11-11", 36.2)]:
        payload = dict(operation_payload, operation_date=day, actual_waste_kg=actual)
        assert client.post("/api/v1/daily-operations", json=payload).status_code == 201
    export = client.post("/api/v1/training-exports").json()
    assert export["status"] == "completed" and export["row_count"] == 3

    summary = run_pipeline(prepared)
    assert summary["version_key"] != old_key

    active = client.get("/api/v1/model/active").json()
    assert active["version_key"] == summary["version_key"]
    op = client.get("/api/v1/daily-operations").json()["items"][0]
    prediction = client.post(f"/api/v1/daily-operations/{op['id']}/predict").json()
    assert prediction["model_version_id"] == active["id"]  # layanan prediksi memuat versi baru

    keys = [v["version_key"] for v in client.get("/api/v1/model/versions").json()]
    assert old_key in keys and summary["version_key"] in keys
    with factory() as db:
        version = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
        sources = {s["kind"] for s in prepared_sources(db, version)}
        hidden = db.scalars(select(EvaluationPrediction).where(
            EvaluationPrediction.model_version_id == version.id,
            EvaluationPrediction.source == "actuals")).all()
    assert sources == {"seed", "actuals"}
    assert len(hidden) == 3  # tanggal terbaru masuk data test
    shown = client.get("/api/v1/model/evaluation-predictions").json()["items"]
    assert all(row["source"] == "seed" for row in shown)


def prepared_sources(db, version):
    from app.models import DatasetVersion, TrainingRun

    run_row = db.get(TrainingRun, version.training_run_id)
    return db.get(DatasetVersion, run_row.dataset_version_id).sources
