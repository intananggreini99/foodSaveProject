"""Pelatihan, prediksi, metrik, dan validasi silang berurutan waktu."""

from __future__ import annotations

import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

from foodsave_core.preprocessing import TARGET, FoodPreprocessor


def make_model(params: dict, n_estimators: int, seed: int) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=n_estimators,
        random_state=seed,
        n_jobs=int(os.environ.get("N_JOBS", "-1")),
        **params,
    )


def fit(train: pd.DataFrame, params: dict, n_estimators: int, seed: int):
    """Preprocessor dan model selalu dilatih dari data yang sama."""
    prep = FoodPreprocessor("robust").fit(train)
    model = make_model(params, n_estimators, seed).fit(prep.transform(train), train[TARGET])
    return prep, model


def predict(prep: FoodPreprocessor, model, frame: pd.DataFrame) -> np.ndarray:
    return np.clip(model.predict(prep.transform(frame)), 0, None)


def metrics(actual, predicted) -> dict[str, float]:
    y = np.asarray(actual, dtype=float)
    p = np.asarray(predicted, dtype=float)
    error = y - p
    mse = float(mean_squared_error(y, p))
    positive = y > 0
    mape = float(np.mean(np.abs(error[positive]) / y[positive]) * 100) if positive.any() else 0.0
    return {
        "mae": float(mean_absolute_error(y, p)),
        "mse": mse,
        "rmse": float(np.sqrt(mse)),
        "mape": mape,
        "r2": float(r2_score(y, p)),
    }


def date_folds(dates: pd.Series, n_splits: int):
    """TimeSeriesSplit di atas tanggal unik: data validasi selalu setelah data latih."""
    unique = np.sort(dates.unique())
    for train_dates, val_dates in TimeSeriesSplit(n_splits=n_splits).split(unique):
        train_idx = np.flatnonzero(dates.isin(unique[train_dates]).to_numpy())
        val_idx = np.flatnonzero(dates.isin(unique[val_dates]).to_numpy())
        yield train_idx, val_idx


def cross_validate(dev: pd.DataFrame, params: dict, n_splits: int, n_estimators: int, seed: int):
    """Preprocessing di-fit ulang di setiap lipatan agar tidak ada kebocoran."""
    fold_scores, oof = [], []
    for fold, (train_idx, val_idx) in enumerate(date_folds(dev["date"], n_splits), start=1):
        train, val = dev.iloc[train_idx], dev.iloc[val_idx]
        prep, model = fit(train, params, n_estimators, seed)
        pred = predict(prep, model, val)
        fold_scores.append(metrics(val[TARGET], pred)["mae"])
        oof.append(
            pd.DataFrame(
                {"date": val["date"].to_numpy(), "actual": val[TARGET].to_numpy(),
                 "predicted": pred, "fold": fold, "source": val["source"].to_numpy()}
            )
        )
    oof = pd.concat(oof, ignore_index=True)
    summary = metrics(oof["actual"], oof["predicted"])
    summary["fold_mae"] = [round(v, 4) for v in fold_scores]
    return summary, oof
