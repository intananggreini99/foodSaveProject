"""Konfigurasi pipeline dari environment."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from sqlalchemy.engine import URL

DEFAULT_GRID = [
    {"max_depth": None, "min_samples_leaf": 1, "max_features": 1.0},
    {"max_depth": None, "min_samples_leaf": 2, "max_features": 0.8},
    {"max_depth": None, "min_samples_leaf": 3, "max_features": 0.6},
    {"max_depth": 12, "min_samples_leaf": 2, "max_features": 0.8},
    {"max_depth": 10, "min_samples_leaf": 3, "max_features": 0.8},
    {"max_depth": 8, "min_samples_leaf": 5, "max_features": 0.6},
]
FAST_GRID = DEFAULT_GRID[:1] + DEFAULT_GRID[4:5]


def _flag(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "ya"}


def database_url() -> str:
    explicit = os.environ.get("DATABASE_URL", "").strip()
    if explicit:
        return explicit
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("POSTGRES_USER", "foodsave"),
        password=os.environ.get("POSTGRES_PASSWORD", ""),
        host=os.environ.get("DATABASE_HOST", "localhost"),
        port=int(os.environ.get("DATABASE_PORT", "5432")),
        database=os.environ.get("POSTGRES_DB", "foodsave"),
    ).render_as_string(hide_password=False)


@dataclass
class PipelineConfig:
    tracking_uri: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    )
    experiment: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_EXPERIMENT", "foodsave-random-forest")
    )
    registered_model_name: str = field(
        default_factory=lambda: os.environ.get("MLFLOW_REGISTERED_MODEL", "foodsave-rf")
    )
    database_url: str = field(default_factory=database_url)
    test_fraction: float = field(
        default_factory=lambda: float(os.environ.get("TEST_FRACTION", "0.2"))
    )
    cv_folds: int = field(default_factory=lambda: int(os.environ.get("CV_FOLDS", "5")))
    n_estimators: int = field(default_factory=lambda: int(os.environ.get("N_ESTIMATORS", "200")))
    seed: int = field(default_factory=lambda: int(os.environ.get("SEED", "42")))
    interval_quantile: float = 0.90
    permutation_repeats: int = 5
    activate: bool = field(default_factory=lambda: _flag("ACTIVATE_MODEL", True))
    grid: list[dict] = field(default_factory=lambda: list(DEFAULT_GRID))

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        config = cls()
        custom = os.environ.get("PARAM_GRID", "").strip()
        if custom:
            config.grid = json.loads(custom)
        if _flag("FOODSAVE_FAST"):
            # Mode cepat untuk tes otomatis; hasilnya tidak untuk produksi.
            config.cv_folds = 3
            config.n_estimators = 30
            config.permutation_repeats = 2
            config.grid = list(FAST_GRID)
        if not 0.05 <= config.test_fraction <= 0.5:
            raise ValueError("TEST_FRACTION harus antara 0.05 dan 0.5.")
        if config.cv_folds < 2:
            raise ValueError("CV_FOLDS minimal 2.")
        return config
