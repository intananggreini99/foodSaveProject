"""Layanan prediksi: model .pkl versi aktif dimuat sekali dari HDFS ke memori.

Alur:
1. Baca baris aktif di model_analysis.model_versions (diisi langkah register MLflow).
2. Bila versi itu belum ada di memori, unduh data_preprocessing.pkl dan
   model_rf_optimize.pkl dari HDFS, cocokkan SHA-256 dengan catatan database,
   lalu simpan di memori proses.
3. Permintaan berikutnya memakai model di memori. Saat versi aktif berganti,
   model baru dimuat otomatis pada permintaan pertama sesudahnya.

File .pkl hanya dibaca dari penyimpanan internal yang ditulis pipeline dan
dicek checksum-nya; aplikasi tidak pernah menerima file pickle dari pengguna.
"""

from __future__ import annotations

import io
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import joblib
from fastapi import HTTPException
from sqlalchemy import select

from app.core import database
from app.models import InferenceLog, ModelVersion
from app.services.common import model_storage
from foodsave_core.features import snapshots_to_frame
from foodsave_core.storage import sha256

log = logging.getLogger("foodsave.prediction")
RANGE_FIELDS = {
    "meals_prepared": "meals_served",
    "kitchen_staff": "kitchen_staff",
    "temperature_c": "temperature_C",
    "humidity_percent": "humidity_percent",
}


@dataclass(frozen=True)
class ActiveModel:
    version_id: UUID
    version_key: str
    interval_radius: Decimal
    training_ranges: dict
    prep: object = field(repr=False)
    model: object = field(repr=False)
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PredictionService:
    def __init__(self):
        self._lock = threading.Lock()
        self._cached: ActiveModel | None = None

    @property
    def cached(self) -> ActiveModel | None:
        return self._cached

    def reset(self) -> None:
        self._cached = None

    @staticmethod
    def active_version(db) -> ModelVersion:
        version = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
        if not version:
            raise HTTPException(
                503,
                "Belum ada model aktif. Jalankan pipeline MLflow (docker compose run --rm trainer).",
            )
        return version

    @staticmethod
    def _load(version: ModelVersion) -> ActiveModel:
        storage = model_storage()
        model_bytes = storage.read_bytes(version.model_path)
        prep_bytes = storage.read_bytes(version.preprocessing_path)
        if sha256(model_bytes) != version.model_sha256:
            raise ValueError("Checksum model_rf_optimize.pkl tidak cocok dengan catatan database.")
        if sha256(prep_bytes) != version.preprocessing_sha256:
            raise ValueError("Checksum data_preprocessing.pkl tidak cocok dengan catatan database.")
        model = joblib.load(io.BytesIO(model_bytes))
        prep = joblib.load(io.BytesIO(prep_bytes))["preprocessor"]
        if model.n_features_in_ != len(prep.columns):
            raise ValueError("Jumlah fitur model dan preprocessing tidak cocok.")
        if hasattr(model, "n_jobs"):
            # Prediksi beberapa baris paling cepat satu thread (sekitar 3x lebih cepat);
            # paralelisme didapat dari banyak permintaan yang dilayani bersamaan.
            model.n_jobs = 1
        return ActiveModel(
            version_id=version.id,
            version_key=version.version_key,
            interval_radius=Decimal(str(version.interval_radius_kg)),
            training_ranges=dict(version.training_ranges or {}),
            prep=prep,
            model=model,
        )

    def get(self, db) -> ActiveModel:
        version = self.active_version(db)
        cached = self._cached
        if cached and cached.version_id == version.id:
            return cached
        with self._lock:
            if self._cached and self._cached.version_id == version.id:
                return self._cached
            try:
                loaded = self._load(version)
            except Exception as exc:
                log.exception("Model %s gagal dimuat", version.version_key)
                raise HTTPException(
                    503, "Model aktif belum bisa dimuat dari penyimpanan. Periksa HDFS dan log."
                ) from exc
            self._cached = loaded
            log.info("Model %s dimuat ke memori", loaded.version_key)
            return loaded

    def reload(self, db) -> ActiveModel:
        """Muat ulang dari HDFS. Bila gagal, model lama di memori tetap dipakai."""
        version = self.active_version(db)
        try:
            loaded = self._load(version)
        except Exception as exc:
            log.exception("Muat ulang model %s gagal", version.version_key)
            raise HTTPException(
                503, "Model gagal dimuat ulang dari HDFS; model di memori tetap dipakai."
            ) from exc
        with self._lock:
            self._cached = loaded
        return loaded

    def predict(self, db, snapshots: list[dict], *, user, source: str):
        """Prediksi satu atau banyak baris sekaligus; setiap panggilan dicatat."""
        started = time.perf_counter()
        active = None
        try:
            active = self.get(db)
            frame = snapshots_to_frame(snapshots)
            raw = active.model.predict(active.prep.transform(frame))
            values = [float(v) for v in raw]
            if not all(math.isfinite(v) for v in values):
                raise ValueError("Prediksi tidak finite.")
        except Exception as exc:
            self._log_failure(user, active, source, len(snapshots), started, exc)
            if isinstance(exc, HTTPException):
                raise
            log.exception("Inferensi gagal")
            raise HTTPException(503, "Prediksi gagal dihitung. Periksa log backend.") from exc
        db.add(
            InferenceLog(
                restaurant_id=user.restaurant_id,
                user_id=user.id,
                model_version_id=active.version_id,
                source=source,
                row_count=len(values),
                duration_ms=Decimal(str(round((time.perf_counter() - started) * 1000, 3))),
                success=True,
            )
        )
        return active, [Decimal(str(max(0.0, v))).quantize(Decimal(".0001")) for v in values]

    @staticmethod
    def _log_failure(user, active, source, rows, started, exc):
        # Sesi terpisah: catatan kegagalan tetap tersimpan walau permintaan di-rollback.
        try:
            with database.SessionLocal() as session:
                session.add(
                    InferenceLog(
                        restaurant_id=user.restaurant_id,
                        user_id=user.id,
                        model_version_id=active.version_id if active else None,
                        source=source,
                        row_count=rows,
                        duration_ms=Decimal(str(round((time.perf_counter() - started) * 1000, 3))),
                        success=False,
                        error_message=(getattr(exc, "detail", None) or type(exc).__name__)[:300],
                    )
                )
                session.commit()
        except Exception:  # noqa: BLE001 - log gagal tidak boleh menutupi error asli
            log.warning("Log inferensi gagal disimpan", exc_info=True)

    @staticmethod
    def outside_training_range(active: ActiveModel, snapshot: dict) -> list[str]:
        """Isian di luar rentang wajar data latih (batas IQR). Prediksi kurang andal."""
        flagged = []
        for app_name, raw_name in RANGE_FIELDS.items():
            bounds = active.training_ranges.get(raw_name)
            if bounds and not bounds[0] <= float(snapshot[app_name]) <= bounds[1]:
                flagged.append(app_name)
        return flagged


prediction_service = PredictionService()
