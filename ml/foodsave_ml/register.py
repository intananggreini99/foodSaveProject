"""Langkah 6: daftarkan model ke MLflow Model Registry dan ke skema model_analysis.

Tabel dibaca lewat refleksi SQLAlchemy, sehingga struktur tabel tetap dikelola
satu sumber: migrasi Alembic di backend/.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import mlflow
from sqlalchemy import MetaData, create_engine, select, update

from foodsave_ml.context import PipelineContext

log = logging.getLogger("foodsave_ml")
SCHEMA = "model_analysis"
TABLES = [
    "dataset_versions",
    "training_runs",
    "tuning_trials",
    "model_versions",
    "model_evaluations",
    "evaluation_predictions",
    "feature_importances",
    "sensitivity_curves",
    "evaluation_reports",
]


def register_mlflow_model(ctx: PipelineContext) -> dict:
    """Daftarkan folder artefak "model" run ini ke Model Registry MLflow."""
    name = ctx.config.registered_model_name
    client = mlflow.MlflowClient()
    try:
        try:
            client.get_registered_model(name)
        except Exception:  # noqa: BLE001 - model belum ada
            client.create_registered_model(
                name, description="Random Forest FoodSave (data_preprocessing.pkl + model_rf_optimize.pkl)"
            )
        version = client.create_model_version(
            name,
            source=f"runs:/{ctx.parent_run_id}/model",
            run_id=ctx.parent_run_id,
            tags={"foodsave.version_key": ctx.version_key},
        )
        if ctx.config.activate:
            client.set_registered_model_alias(name, "aktif", version.version)
        return {"name": name, "version": str(version.version)}
    except Exception as exc:  # noqa: BLE001 - registry opsional, catatan DB tetap jalan
        log.warning("MLflow Model Registry dilewati: %s", exc)
        return {"name": None, "version": None}


def _new_id():
    return uuid.uuid4()


def write_model_analysis(ctx: PipelineContext, mlflow_info: dict) -> dict:
    engine = create_engine(ctx.config.database_url, pool_pre_ping=True)
    meta = MetaData()
    meta.reflect(engine, schema=SCHEMA, only=TABLES)
    t = {name: meta.tables[f"{SCHEMA}.{name}"] for name in TABLES}
    now = datetime.now(timezone.utc)
    dev, test, manifest = ctx.dev, ctx.test, ctx.manifest
    try:
        with engine.begin() as conn:
            dataset_id = conn.scalar(
                select(t["dataset_versions"].c.id).where(
                    t["dataset_versions"].c.fingerprint == ctx.fingerprint
                )
            )
            if dataset_id is None:
                dataset_id = _new_id()
                conn.execute(
                    t["dataset_versions"].insert().values(
                        id=dataset_id,
                        fingerprint=ctx.fingerprint,
                        sources=[s.__dict__ for s in ctx.sources],
                        raw_rows=ctx.audit["raw_rows"],
                        usable_rows=ctx.audit["usable_rows"],
                        invalid_removed=ctx.audit["invalid_removed"],
                        duplicates_removed=ctx.audit["duplicates_removed"],
                        date_start=ctx.audit["date_start"],
                        date_end=ctx.audit["date_end"],
                    )
                )

            run_id = _new_id()
            conn.execute(
                t["training_runs"].insert().values(
                    id=run_id,
                    mlflow_run_id=ctx.parent_run_id,
                    mlflow_experiment_id=ctx.experiment_id,
                    dataset_version_id=dataset_id,
                    status="completed",
                    processed_path=ctx.processed_path,
                    dev_rows=len(dev),
                    test_rows=len(test),
                    dev_start=dev.date.min().date(),
                    dev_end=dev.date.max().date(),
                    test_start=test.date.min().date(),
                    test_end=test.date.max().date(),
                    cv_folds=ctx.config.cv_folds,
                    selection_rule="MAE validasi silang berurutan waktu terkecil pada 80% data awal;"
                    " seri dipecah dengan RMSE. Data test 20% tidak dipakai untuk memilih.",
                    best_params=ctx.best.params,
                    started_at=ctx.started_at,
                    finished_at=now,
                )
            )
            conn.execute(
                t["tuning_trials"].insert(),
                [
                    {
                        "id": _new_id(),
                        "training_run_id": run_id,
                        "trial_number": trial.number,
                        "stage": trial.stage,
                        "params": trial.params,
                        "cv_mae": trial.cv["mae"],
                        "cv_mse": trial.cv["mse"],
                        "cv_rmse": trial.cv["rmse"],
                        "cv_mape": trial.cv["mape"],
                        "cv_r2": trial.cv["r2"],
                        "fold_mae": trial.cv["fold_mae"],
                        "is_best": trial.is_best,
                        "mlflow_run_id": trial.mlflow_run_id,
                    }
                    for trial in ctx.trials
                ],
            )

            if ctx.config.activate:
                # Lepaskan versi aktif lama dulu (indeks unik parsial is_active).
                conn.execute(
                    update(t["model_versions"])
                    .where(t["model_versions"].c.is_active.is_(True))
                    .values(is_active=False)
                )
            version_id = _new_id()
            conn.execute(
                t["model_versions"].insert().values(
                    id=version_id,
                    version_key=ctx.version_key,
                    name="RandomForest",
                    training_run_id=run_id,
                    params={**manifest["params"], "n_estimators": manifest["n_estimators"]},
                    storage_dir=manifest["storage_dir"],
                    model_path=manifest["model_path"],
                    preprocessing_path=manifest["preprocessing_path"],
                    manifest_path=ctx.artifacts["paths"]["manifest"],
                    model_sha256=manifest["model_sha256"],
                    preprocessing_sha256=manifest["preprocessing_sha256"],
                    input_features=manifest["input_features"],
                    feature_columns=manifest["feature_columns"],
                    training_ranges=manifest["training_ranges"],
                    interval_radius_kg=manifest["interval_radius_kg"],
                    default_safe_max_kg=manifest["default_safe_max_kg"],
                    default_warning_max_kg=manifest["default_warning_max_kg"],
                    trained_rows=manifest["trained_rows"],
                    trained_from=manifest["trained_from"],
                    trained_to=manifest["trained_to"],
                    sklearn_version=manifest["sklearn_version"],
                    mlflow_run_id=ctx.parent_run_id,
                    mlflow_model_name=mlflow_info.get("name"),
                    mlflow_model_version=mlflow_info.get("version"),
                    metrics=manifest["metrics"],
                    is_active=ctx.config.activate,
                    activated_at=now if ctx.config.activate else None,
                )
            )
            conn.execute(
                t["model_evaluations"].insert(),
                [
                    {
                        "id": _new_id(),
                        "model_version_id": version_id,
                        "scope": scope,
                        "n_rows": values["n_rows"],
                        "mae": values["mae"],
                        "mse": values["mse"],
                        "rmse": values["rmse"],
                        "mape": values["mape"],
                        "r2": values["r2"],
                        "interval_coverage": values["interval_coverage"],
                    }
                    for scope, values in ctx.evaluation.items()
                ],
            )
            predictions = [
                {
                    "id": _new_id(),
                    "model_version_id": version_id,
                    "scope": "oof_dev",
                    "source": row.source,
                    "observation_date": row.date.date(),
                    "fold": int(row.fold),
                    "actual_kg": float(row.actual),
                    "predicted_kg": float(row.predicted),
                    "error_kg": float(row.actual - row.predicted),
                }
                for row in ctx.best.oof.itertuples()
            ] + [
                {
                    "id": _new_id(),
                    "model_version_id": version_id,
                    "scope": "test",
                    "source": row.source,
                    "observation_date": row.date.date(),
                    "fold": None,
                    "actual_kg": float(row.actual),
                    "predicted_kg": float(row.predicted),
                    "error_kg": float(row.actual - row.predicted),
                }
                for row in ctx.test_predictions.itertuples()
            ]
            conn.execute(t["evaluation_predictions"].insert(), predictions)
            conn.execute(
                t["feature_importances"].insert(),
                [
                    {
                        "id": _new_id(),
                        "model_version_id": version_id,
                        "feature": row.feature,
                        "importance_mae": float(row.importance_mae),
                        "importance_std": float(row.importance_std),
                        "rank": int(row.rank),
                    }
                    for row in ctx.importances.itertuples()
                ],
            )
            conn.execute(
                t["sensitivity_curves"].insert(),
                [
                    {
                        "id": _new_id(),
                        "model_version_id": version_id,
                        "staff_experience": row.staff_experience,
                        "special_event": bool(row.special_event),
                        "meals_prepared": int(row.meals_served),
                        "predicted_kg": float(row.predicted_kg),
                        "within_training_range": bool(row.within_training_range),
                    }
                    for row in ctx.sensitivity.itertuples()
                ],
            )
            conn.execute(
                t["evaluation_reports"].insert(),
                [
                    {
                        "id": _new_id(),
                        "model_version_id": version_id,
                        "file_format": fmt,
                        "storage_path": info["path"],
                        "sha256": info["sha256"],
                        "size_bytes": info["size"],
                    }
                    for fmt, info in ctx.reports.items()
                ],
            )
    finally:
        engine.dispose()
    return {"model_version_id": str(version_id), "training_run_id": str(run_id),
            "dataset_version_id": str(dataset_id)}
