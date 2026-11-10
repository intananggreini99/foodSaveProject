"""Validasi artefak, pemetaan input API, dan metrik holdout yang tersimpan."""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
from types import SimpleNamespace
import joblib
import numpy as np
import pandas as pd
from api.config import ROOT, get_settings
from api.services import artifact_path, digest, predict_value


def check(database=False):
    manifest = json.loads(get_settings().model_manifest.read_text(encoding="utf-8"))
    model_path = artifact_path(manifest["model_path"])
    prep_path = artifact_path(manifest["preprocessing_path"])
    model = joblib.load(model_path)
    bundle = joblib.load(prep_path)
    prep = bundle["preprocessor"]
    assert manifest["model"] == "RandomForest" and bundle["name"] == "RandomForest"
    assert model.n_features_in_ == len(prep.columns)
    assert list(model.feature_names_in_) == prep.columns
    assert not {
        "ID",
        "food_waste_kg",
        "actual_waste_kg",
        "past_waste_kg",
        "waste_category",
    }.intersection(prep.columns)
    versions = {
        name: importlib.metadata.version(name)
        for name in ["numpy", "pandas", "scikit-learn", "joblib"]
    }
    environment = ROOT / "results/evaluation/environment.json"
    if environment.exists():
        trained = json.loads(environment.read_text())["packages"]
        for name, value in versions.items():
            assert value == trained[name], f"Versi {name} berbeda dari lingkungan training."
    version = SimpleNamespace(
        name=manifest["model"],
        artifact_path=manifest["model_path"],
        preprocessing_path=manifest["preprocessing_path"],
        artifact_sha256=digest(model_path),
        preprocessing_sha256=digest(prep_path),
    )
    snapshot = {
        "operation_date": "2026-11-11",
        "meals_prepared": 400,
        "kitchen_staff": 12,
        "staff_experience": "intermediate",
        "special_event": False,
        "temperature_c": 28,
        "humidity_percent": 65,
    }
    raw = pd.DataFrame(
        [
            {
                "date": snapshot["operation_date"],
                "meals_served": 400,
                "kitchen_staff": 12,
                "staff_experience": "intermediate",
                "special_event": 0,
                "temperature_C": 28,
                "humidity_percent": 65,
            }
        ]
    )
    direct = float(model.predict(prep.transform(raw))[0])
    from_api = float(predict_value(snapshot, version))
    assert abs(max(0, direct) - from_api) <= 0.0001
    modified = raw.assign(food_waste_kg=999999, past_waste_kg=999999, waste_category="unknown")
    pd.testing.assert_frame_equal(prep.transform(raw), prep.transform(modified))
    output = {
        "status": "passed",
        "model": manifest["model"],
        "preprocessing": manifest["preprocessing"],
        "feature_count": len(prep.columns),
        "artifact_sha256": version.artifact_sha256,
        "preprocessing_sha256": version.preprocessing_sha256,
        "packages": versions,
        "api_mapping_check": "passed",
        "target_leakage_check": "passed",
        "sample_prediction_kg": from_api,
    }
    label = f"{manifest['model']}_{manifest['preprocessing']}"
    reference = ROOT / f"results/evaluation/{label}_test_predictions.csv"
    raw_path = ROOT / "dataset/raw/train.csv"
    if reference.exists() and raw_path.exists():
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

        expected = pd.read_csv(reference)
        source = pd.read_csv(raw_path).iloc[expected["row"].astype(int)].copy()
        actual = model.predict(prep.transform(source))
        np.testing.assert_allclose(actual, expected.prediction, rtol=1e-5, atol=1e-5)
        score = {
            "MAE": float(mean_absolute_error(expected.actual, actual)),
            "RMSE": float(np.sqrt(mean_squared_error(expected.actual, actual))),
            "R2": float(r2_score(expected.actual, actual)),
        }
        for metric, value in score.items():
            assert np.isclose(value, manifest[f"test_{metric}"])
        output["holdout_recheck"] = {"status": "passed", "rows": len(expected), **score}
    else:
        output["holdout_recheck"] = {
            "status": "not_available",
            "note": "Dataset mentah/reference tidak ada; pengecekan artefak dan pemetaan API tetap dilakukan.",
        }
    results = ROOT / "results/evaluation/experiment_results.csv"
    if results.exists():
        table = pd.read_csv(results).sort_values(
            ["validation_MAE", "validation_RMSE", "validation_ms_per_row"]
        )
        best = table.iloc[0]
        assert (best.model, best.preprocessing) == (manifest["model"], manifest["preprocessing"])
        output["selection_check"] = "passed: MAE validasi, bukan MAE test"
    if database:
        from sqlalchemy import select
        from api.database import SessionLocal
        from api.models import ModelVersion

        with SessionLocal() as db:
            active = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
            assert (
                active
                and active.artifact_sha256 == version.artifact_sha256
                and active.preprocessing_sha256 == version.preprocessing_sha256
            )
            assert (active.name, active.preprocessing) == (
                manifest["model"],
                manifest["preprocessing"],
            )
            output["database_model_version_id"] = str(active.id)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", action="store_true")
    result = check(parser.parse_args().database)
    print(json.dumps(result, indent=2))
    folder = ROOT / "results"
    if folder.exists() and os.access(folder, os.W_OK):
        folder = folder / "backend"
        folder.mkdir(exist_ok=True)
        (folder / "backend-model-check.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8"
        )
