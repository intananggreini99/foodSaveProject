"""Wadah hasil antar-langkah pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

from foodsave_core.storage import Storage
from foodsave_ml.config import PipelineConfig
from foodsave_ml.data import Source


@dataclass
class Trial:
    number: int
    stage: str  # baseline (langkah 2) atau tuning (langkah 3)
    params: dict
    cv: dict
    oof: pd.DataFrame
    mlflow_run_id: str | None = None
    is_best: bool = False


@dataclass
class PipelineContext:
    config: PipelineConfig
    storage: Storage
    started_at: datetime
    version_key: str
    parent_run_id: str | None = None
    experiment_id: str | None = None
    # langkah 1
    sources: list[Source] = field(default_factory=list)
    audit: dict = field(default_factory=dict)
    data: pd.DataFrame | None = None
    fingerprint: str = ""
    processed_path: str = ""
    # langkah 2-3
    trials: list[Trial] = field(default_factory=list)
    best: Trial | None = None
    # langkah 4
    evaluation: dict[str, Any] = field(default_factory=dict)
    test_predictions: pd.DataFrame | None = None
    importances: pd.DataFrame | None = None
    interval_radius: float = 0.0
    reports: dict[str, dict] = field(default_factory=dict)
    # langkah 5
    artifacts: dict[str, Any] = field(default_factory=dict)
    sensitivity: pd.DataFrame | None = None
    manifest: dict = field(default_factory=dict)
    # langkah 6
    registered: dict = field(default_factory=dict)

    @property
    def dev(self) -> pd.DataFrame:
        return self.data[self.data.split == "dev"].reset_index(drop=True)

    @property
    def test(self) -> pd.DataFrame:
        return self.data[self.data.split == "test"].reset_index(drop=True)
