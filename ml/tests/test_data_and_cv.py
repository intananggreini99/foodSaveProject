"""Tes pipeline tanpa database: pembersihan, split waktu, validasi silang, dan file .pkl.

Jalankan: python -m pytest ml/tests
"""

import io
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from foodsave_core.storage import RAW_ACTUALS_DIR, RAW_SEED, LocalStorage, ensure_layout  # noqa: E402
from foodsave_ml import data, modeling  # noqa: E402


@pytest.fixture
def storage(tmp_path):
    store = LocalStorage(tmp_path)
    ensure_layout(store)
    store.write_bytes(RAW_SEED, (ROOT / "dataset/raw/train.csv").read_bytes())
    return store


def test_temporal_split_keeps_test_dates_after_dev(storage):
    frames, sources = data.read_sources(storage)
    df, audit = data.clean(frames)
    split = data.temporal_split(df, 0.2)
    dev, test = split[split.split == "dev"], split[split.split == "test"]
    assert dev.date.max() < test.date.min()
    assert 0.17 < len(test) / len(split) < 0.23
    assert audit["usable_rows"] == len(df) and sources[0].kind == "seed"


def test_latest_export_of_an_operation_wins(storage):
    header = ("ID,date,meals_served,kitchen_staff,temperature_C,humidity_percent,day_of_week,"
              "special_event,past_waste_kg,staff_experience,waste_category,food_waste_kg,"
              "source,operation_id,restaurant_ref,exported_at\n")
    first = header + ",2026-11-01,300,10,27,70,6,0,,beginner,meat,20,actuals,op-1,r1,2026-11-02T00:00:00\n"
    second = header + ",2026-11-01,300,10,27,70,6,0,,beginner,meat,25,actuals,op-1,r1,2026-11-03T00:00:00\n"
    storage.write_bytes(f"{RAW_ACTUALS_DIR}/a.csv", first.encode())
    storage.write_bytes(f"{RAW_ACTUALS_DIR}/b.csv", second.encode())
    frames, sources = data.read_sources(storage)
    df, audit = data.clean(frames)
    actual_rows = df[df.source == "actuals"]
    assert len(sources) == 3 and len(actual_rows) == 1
    assert actual_rows.iloc[0].food_waste_kg == 25 and audit["duplicates_removed"] >= 1


def test_cv_folds_validate_only_on_later_dates(storage):
    frames, _ = data.read_sources(storage)
    df, _ = data.clean(frames)
    for train_idx, val_idx in modeling.date_folds(df["date"], 4):
        assert df.date.iloc[train_idx].max() < df.date.iloc[val_idx].min()


def test_pickles_reload_with_shared_preprocessor(storage):
    frames, _ = data.read_sources(storage)
    df, _ = data.clean(frames)
    prep, model = modeling.fit(df.head(300), {"max_depth": 6}, 20, 42)
    buffer_model, buffer_prep = io.BytesIO(), io.BytesIO()
    joblib.dump(model, buffer_model)
    joblib.dump({"preprocessor": prep}, buffer_prep)
    loaded_model = joblib.load(io.BytesIO(buffer_model.getvalue()))
    loaded_prep = joblib.load(io.BytesIO(buffer_prep.getvalue()))["preprocessor"]
    assert type(loaded_prep).__module__ == "foodsave_core.preprocessing"
    sample = df.tail(5)
    np.testing.assert_allclose(
        modeling.predict(loaded_prep, loaded_model, sample), modeling.predict(prep, model, sample)
    )


def test_metrics_skip_zero_targets_for_mape():
    result = modeling.metrics(pd.Series([0.0, 10.0]), np.array([1.0, 12.0]))
    assert result["mape"] == pytest.approx(20.0) and result["mae"] == pytest.approx(1.5)
