"""Enam langkah pipeline MLflow sesuai diagram arsitektur FoodSave.

1. data_preprocessing             baca raw dari HDFS, bersihkan, bagi waktu 80/20
2. train_rf_model                 model dasar, validasi silang berurutan waktu
3. optimasi_parameter_rf_model    coba kombinasi parameter, pilih MAE CV terkecil
4. analisis_data_model_rf_optimize  uji SEKALI di test 20%, laporan evaluasi ke HDFS
5. create_file_pkl                latih ulang dengan semua data, simpan .pkl ke HDFS
6. register_model                 isi skema model_analysis dan tandai versi aktif

Data test tidak pernah dipakai untuk memilih parameter. Model final di langkah 5
memakai semua data, tetapi metrik yang dilaporkan tetap berasal dari langkah 4.
"""

from __future__ import annotations

import io
import json
import logging

import joblib
import mlflow
import numpy as np
import pandas as pd
import sklearn
from sklearn.inspection import permutation_importance

from foodsave_core.features import MODEL_INPUT_FIELDS
from foodsave_core.preprocessing import EXPERIENCE_LEVELS, TARGET
from foodsave_core.storage import EVAL_REPORTS_DIR, MODELS_DIR, PROCESSED_DIR, sha256
from foodsave_ml import data as data_mod
from foodsave_ml import modeling
from foodsave_ml.context import PipelineContext, Trial

log = logging.getLogger("foodsave_ml")


def _log_metrics(prefix: str, values: dict):
    mlflow.log_metrics({f"{prefix}_{k}": v for k, v in values.items() if isinstance(v, float)})


# 1 ---------------------------------------------------------------------------
def data_preprocessing(ctx: PipelineContext) -> None:
    frames, ctx.sources = data_mod.read_sources(ctx.storage)
    df, ctx.audit = data_mod.clean(frames)
    ctx.data = data_mod.temporal_split(df, ctx.config.test_fraction)
    ctx.fingerprint = data_mod.fingerprint(ctx.sources)

    run_dir = f"{PROCESSED_DIR}/{ctx.version_key}"
    ctx.processed_path = f"{run_dir}/data_bersih.csv"
    export = ctx.data.drop(columns=["_order"]).copy()
    export["date"] = export["date"].dt.strftime("%Y-%m-%d")
    ctx.storage.makedirs(run_dir)
    ctx.storage.write_bytes(ctx.processed_path, export.to_csv(index=False).encode())

    dev, test = ctx.dev, ctx.test
    mlflow.log_params(
        {
            "sumber_data": len(ctx.sources),
            "baris_mentah": ctx.audit["raw_rows"],
            "baris_dipakai": ctx.audit["usable_rows"],
            "baris_tidak_valid": ctx.audit["invalid_removed"],
            "duplikat_dihapus": ctx.audit["duplicates_removed"],
            "test_fraction": ctx.config.test_fraction,
            "dev_rows": len(dev),
            "test_rows": len(test),
            "dev_range": f"{dev.date.min().date()}..{dev.date.max().date()}",
            "test_range": f"{test.date.min().date()}..{test.date.max().date()}",
            "processed_path": ctx.processed_path,
            "dataset_fingerprint": ctx.fingerprint[:16],
        }
    )
    log.info("Data: %s baris dipakai (dev %s, test %s)", len(ctx.data), len(dev), len(test))


def _run_trial(ctx: PipelineContext, number: int, stage: str, params: dict) -> Trial:
    cfg = ctx.config
    with mlflow.start_run(run_name=f"trial_{number}", nested=True) as run:
        mlflow.log_params({**{k: str(v) for k, v in params.items()}, "stage": stage,
                           "n_estimators": cfg.n_estimators, "cv_folds": cfg.cv_folds})
        cv, oof = modeling.cross_validate(
            ctx.dev, params, cfg.cv_folds, cfg.n_estimators, cfg.seed
        )
        _log_metrics("cv", cv)
        trial = Trial(number, stage, params, cv, oof, run.info.run_id)
    log.info("Trial %s %s: MAE CV %.3f", number, params, cv["mae"])
    return trial


# 2 ---------------------------------------------------------------------------
def train_rf_model(ctx: PipelineContext) -> None:
    baseline = ctx.config.grid[0]
    trial = _run_trial(ctx, 0, "baseline", baseline)
    ctx.trials.append(trial)
    _log_metrics("baseline_cv", trial.cv)


# 3 ---------------------------------------------------------------------------
def optimasi_parameter(ctx: PipelineContext) -> None:
    for number, params in enumerate(ctx.config.grid[1:], start=1):
        ctx.trials.append(_run_trial(ctx, number, "tuning", params))
    # Aturan pemilihan: MAE CV terkecil, seri dipecah dengan RMSE CV.
    ctx.best = min(ctx.trials, key=lambda t: (round(t.cv["mae"], 6), t.cv["rmse"]))
    ctx.best.is_best = True
    mlflow.log_params({f"best_{k}": str(v) for k, v in ctx.best.params.items()})
    mlflow.log_param("best_trial", ctx.best.number)
    _log_metrics("best_cv", ctx.best.cv)


# 4 ---------------------------------------------------------------------------
def analisis_model(ctx: PipelineContext) -> None:
    from foodsave_ml.reporting import build_pdf, build_xlsx

    cfg, dev, test = ctx.config, ctx.dev, ctx.test
    prep, model = modeling.fit(dev, ctx.best.params, cfg.n_estimators, cfg.seed)
    pred = modeling.predict(prep, model, test)
    test_metrics = modeling.metrics(test[TARGET], pred)
    baseline_pred = np.full(len(test), float(dev[TARGET].median()))
    baseline_metrics = modeling.metrics(test[TARGET], baseline_pred)

    # Rentang estimasi dari residual out-of-fold, lalu dicek cakupannya di test.
    oof = ctx.best.oof
    ctx.interval_radius = float(np.quantile(np.abs(oof.actual - oof.predicted), cfg.interval_quantile))
    coverage = float(np.mean(np.abs(test[TARGET].to_numpy() - pred) <= ctx.interval_radius))

    importance = permutation_importance(
        model,
        prep.transform(test),
        test[TARGET],
        scoring="neg_mean_absolute_error",
        n_repeats=cfg.permutation_repeats,
        random_state=cfg.seed,
    )
    ctx.importances = (
        pd.DataFrame(
            {"feature": prep.columns, "importance_mae": importance.importances_mean,
             "importance_std": importance.importances_std}
        )
        .sort_values("importance_mae", ascending=False)
        .reset_index(drop=True)
    )
    ctx.importances["rank"] = np.arange(1, len(ctx.importances) + 1)
    ctx.test_predictions = pd.DataFrame(
        {"date": test["date"].to_numpy(), "actual": test[TARGET].to_numpy(), "predicted": pred,
         "source": test["source"].to_numpy()}
    )
    ctx.evaluation = {
        "cv_dev": {**{k: v for k, v in ctx.best.cv.items() if k != "fold_mae"},
                   "n_rows": len(oof), "interval_coverage": None},
        "test": {**test_metrics, "n_rows": len(test), "interval_coverage": coverage},
        "baseline_test": {**baseline_metrics, "n_rows": len(test), "interval_coverage": None},
    }
    _log_metrics("test", test_metrics)
    _log_metrics("baseline_test", baseline_metrics)
    mlflow.log_metrics({"interval_radius_kg": ctx.interval_radius, "test_interval_coverage": coverage})

    report_dir = f"{EVAL_REPORTS_DIR}/{ctx.version_key}"
    ctx.storage.makedirs(report_dir)
    for fmt, builder in (("xlsx", build_xlsx), ("pdf", build_pdf)):
        content = builder(ctx)
        path = f"{report_dir}/laporan_evaluasi.{fmt}"
        ctx.storage.write_bytes(path, content)
        ctx.reports[fmt] = {"path": path, "sha256": sha256(content), "size": len(content)}
        _log_bytes(f"laporan_evaluasi.{fmt}", content, "laporan_evaluasi")
    log.info("Test MAE %.3f (baseline %.3f)", test_metrics["mae"], baseline_metrics["mae"])


def _log_bytes(name: str, content: bytes, artifact_path: str, run_id: str | None = None):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / name
        file.write_bytes(content)
        if run_id:
            mlflow.MlflowClient().log_artifact(run_id, str(file), artifact_path=artifact_path)
        else:
            mlflow.log_artifact(str(file), artifact_path=artifact_path)


# 5 ---------------------------------------------------------------------------
def create_file_pkl(ctx: PipelineContext) -> None:
    cfg, full = ctx.config, ctx.data
    prep, model = modeling.fit(full, ctx.best.params, cfg.n_estimators, cfg.seed)

    model_buffer, prep_buffer = io.BytesIO(), io.BytesIO()
    joblib.dump(model, model_buffer)
    joblib.dump({"preprocessor": prep, "version": ctx.version_key}, prep_buffer)
    model_bytes, prep_bytes = model_buffer.getvalue(), prep_buffer.getvalue()

    # Batas risiko awal = tertil target semua data (bisa diubah per restoran).
    safe, warning = (float(round(v, 2)) for v in full[TARGET].quantile([1 / 3, 2 / 3]))
    if warning <= safe:
        warning = safe + 1.0
    ctx.sensitivity = _sensitivity(prep, model, full)

    storage_dir = f"{MODELS_DIR}/{ctx.version_key}"
    paths = {
        "model": f"{storage_dir}/model_rf_optimize.pkl",
        "preprocessing": f"{storage_dir}/data_preprocessing.pkl",
        "manifest": f"{storage_dir}/manifest.json",
    }
    ctx.manifest = {
        "version_key": ctx.version_key,
        "name": "RandomForest",
        "params": ctx.best.params,
        "n_estimators": cfg.n_estimators,
        "storage_dir": storage_dir,
        "model_path": paths["model"],
        "preprocessing_path": paths["preprocessing"],
        "model_sha256": sha256(model_bytes),
        "preprocessing_sha256": sha256(prep_bytes),
        "input_features": MODEL_INPUT_FIELDS,
        "feature_columns": prep.columns,
        "training_ranges": {k: list(v) for k, v in prep.training_range().items()},
        "interval_radius_kg": round(ctx.interval_radius, 4),
        "default_safe_max_kg": safe,
        "default_warning_max_kg": warning,
        "trained_rows": len(full),
        "trained_from": str(full.date.min().date()),
        "trained_to": str(full.date.max().date()),
        "sklearn_version": sklearn.__version__,
        "mlflow_run_id": ctx.parent_run_id,
        "metrics": {
            "test_mae": ctx.evaluation["test"]["mae"],
            "test_rmse": ctx.evaluation["test"]["rmse"],
            "test_mape": ctx.evaluation["test"]["mape"],
            "test_r2": ctx.evaluation["test"]["r2"],
            "cv_mae": ctx.evaluation["cv_dev"]["mae"],
            "baseline_test_mae": ctx.evaluation["baseline_test"]["mae"],
            "test_interval_coverage": ctx.evaluation["test"]["interval_coverage"],
        },
        "note": "Metrik berasal dari model yang dilatih pada 80% data awal dan diuji sekali "
        "pada 20% data terakhir. File .pkl ini dilatih ulang dengan semua data.",
    }
    manifest_bytes = json.dumps(ctx.manifest, indent=2, default=str).encode()
    ctx.storage.makedirs(storage_dir)
    ctx.storage.write_bytes(paths["preprocessing"], prep_bytes)
    ctx.storage.write_bytes(paths["model"], model_bytes)
    ctx.storage.write_bytes(paths["manifest"], manifest_bytes)
    ctx.artifacts = {"paths": paths, "storage_dir": storage_dir}
    for name, content in (
        ("model_rf_optimize.pkl", model_bytes),
        ("data_preprocessing.pkl", prep_bytes),
        ("manifest.json", manifest_bytes),
    ):
        # Di run induk, agar Model Registry (runs:/<induk>/model) menunjuk ke file ini.
        _log_bytes(name, content, "model", run_id=ctx.parent_run_id)
    mlflow.log_params({"trained_rows": len(full), "storage_dir": storage_dir})
    log.info("Model final disimpan di %s", storage_dir)


def _sensitivity(prep, model, full: pd.DataFrame) -> pd.DataFrame:
    """Kurva prediksi terhadap jumlah porsi; kondisi lain di median data."""
    reference_date = full["date"].max()
    while reference_date.day_of_week >= 5:
        reference_date -= pd.Timedelta(days=1)
    staff = int(round(pd.to_numeric(full["kitchen_staff"], errors="coerce").median()))
    temp = float(pd.to_numeric(full["temperature_C"], errors="coerce").median())
    humidity = float(pd.to_numeric(full["humidity_percent"], errors="coerce").median())
    low, high = prep.training_range().get("meals_served", (0, float("inf")))
    rows = []
    for experience in EXPERIENCE_LEVELS:
        for event in (0, 1):
            for meals in range(50, 801, 25):
                rows.append(
                    {"date": reference_date.strftime("%Y-%m-%d"), "meals_served": meals,
                     "kitchen_staff": staff, "staff_experience": experience,
                     "special_event": event, "temperature_C": temp, "humidity_percent": humidity}
                )
    grid = pd.DataFrame(rows)
    grid["predicted_kg"] = modeling.predict(prep, model, grid)
    grid["within_training_range"] = grid["meals_served"].between(low, high)
    return grid


# 6 ---------------------------------------------------------------------------
def register_model(ctx: PipelineContext) -> None:
    from foodsave_ml.register import register_mlflow_model, write_model_analysis

    mlflow_info = register_mlflow_model(ctx)
    ctx.registered = write_model_analysis(ctx, mlflow_info)
    mlflow.set_tags(
        {"foodsave.version_key": ctx.version_key, "foodsave.active": str(ctx.config.activate)}
    )
    log.info("Versi %s terdaftar (aktif=%s)", ctx.version_key, ctx.config.activate)


STEPS = [
    ("data_preprocessing", data_preprocessing),
    ("train_rf_model", train_rf_model),
    ("optimasi_parameter_rf_model", optimasi_parameter),
    ("analisis_data_model_rf_optimize", analisis_model),
    ("create_file_pkl", create_file_pkl),
    ("register_model", register_model),
]
