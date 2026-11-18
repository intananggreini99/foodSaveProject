"""Skema model_analysis: hasil analisis statis yang diisi langkah "register model" MLflow.

FastAPI hanya membaca skema ini (halaman Insight, Pengaturan, laporan evaluasi)
dan memakai model_versions untuk mengetahui file .pkl mana yang aktif di HDFS.
Pipeline ml/ menulis ke tabel-tabel ini lewat SQLAlchemy Core (refleksi tabel).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import JSON_DATA, KG, MA, Identity


class DatasetVersion(Identity, Base):
    __tablename__ = "dataset_versions"
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    sources: Mapped[list] = mapped_column(JSON_DATA)
    raw_rows: Mapped[int] = mapped_column(Integer)
    usable_rows: Mapped[int] = mapped_column(Integer)
    invalid_removed: Mapped[int] = mapped_column(Integer)
    duplicates_removed: Mapped[int] = mapped_column(Integer)
    date_start: Mapped[date] = mapped_column(Date)
    date_end: Mapped[date] = mapped_column(Date)
    __table_args__ = {"schema": MA}


class TrainingRun(Identity, Base):
    __tablename__ = "training_runs"
    mlflow_run_id: Mapped[str] = mapped_column(String(64), unique=True)
    mlflow_experiment_id: Mapped[str | None] = mapped_column(String(64))
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.dataset_versions.id")
    )
    status: Mapped[str] = mapped_column(String(20), default="completed")
    processed_path: Mapped[str] = mapped_column(String(500))
    dev_rows: Mapped[int] = mapped_column(Integer)
    test_rows: Mapped[int] = mapped_column(Integer)
    dev_start: Mapped[date] = mapped_column(Date)
    dev_end: Mapped[date] = mapped_column(Date)
    test_start: Mapped[date] = mapped_column(Date)
    test_end: Mapped[date] = mapped_column(Date)
    cv_folds: Mapped[int] = mapped_column(Integer)
    selection_rule: Mapped[str] = mapped_column(Text)
    best_params: Mapped[dict] = mapped_column(JSON_DATA)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("status IN ('completed','failed')", name="status"),
        CheckConstraint("dev_end < test_start", name="temporal_split"),
        {"schema": MA},
    )


class TuningTrial(Identity, Base):
    __tablename__ = "tuning_trials"
    training_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.training_runs.id", ondelete="CASCADE")
    )
    trial_number: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(20))
    params: Mapped[dict] = mapped_column(JSON_DATA)
    cv_mae: Mapped[float] = mapped_column(Float)
    cv_mse: Mapped[float] = mapped_column(Float)
    cv_rmse: Mapped[float] = mapped_column(Float)
    cv_mape: Mapped[float] = mapped_column(Float)
    cv_r2: Mapped[float] = mapped_column(Float)
    fold_mae: Mapped[list] = mapped_column(JSON_DATA)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False)
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("training_run_id", "trial_number"),
        CheckConstraint("stage IN ('baseline','tuning')", name="stage"),
        {"schema": MA},
    )


class ModelVersion(Identity, Base):
    __tablename__ = "model_versions"
    version_key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(80), default="RandomForest")
    training_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{MA}.training_runs.id")
    )
    params: Mapped[dict] = mapped_column(JSON_DATA)
    storage_dir: Mapped[str] = mapped_column(String(500))
    model_path: Mapped[str] = mapped_column(String(500))
    preprocessing_path: Mapped[str] = mapped_column(String(500))
    manifest_path: Mapped[str] = mapped_column(String(500))
    model_sha256: Mapped[str] = mapped_column(String(64))
    preprocessing_sha256: Mapped[str] = mapped_column(String(64))
    input_features: Mapped[list] = mapped_column(JSON_DATA)
    feature_columns: Mapped[list] = mapped_column(JSON_DATA)
    training_ranges: Mapped[dict] = mapped_column(JSON_DATA)
    interval_radius_kg: Mapped[Decimal] = mapped_column(KG)
    default_safe_max_kg: Mapped[Decimal] = mapped_column(KG)
    default_warning_max_kg: Mapped[Decimal] = mapped_column(KG)
    trained_rows: Mapped[int] = mapped_column(Integer)
    trained_from: Mapped[date] = mapped_column(Date)
    trained_to: Mapped[date] = mapped_column(Date)
    sklearn_version: Mapped[str] = mapped_column(String(20))
    mlflow_run_id: Mapped[str | None] = mapped_column(String(64))
    mlflow_model_name: Mapped[str | None] = mapped_column(String(120))
    mlflow_model_version: Mapped[str | None] = mapped_column(String(20))
    metrics: Mapped[dict] = mapped_column(JSON_DATA)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        Index(
            "uq_model_versions_single_active",
            "is_active",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        CheckConstraint(
            "interval_radius_kg >= 0 AND default_warning_max_kg > default_safe_max_kg",
            name="values",
        ),
        {"schema": MA},
    )


class ModelEvaluation(Identity, Base):
    __tablename__ = "model_evaluations"
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id", ondelete="CASCADE")
    )
    scope: Mapped[str] = mapped_column(String(20))
    n_rows: Mapped[int] = mapped_column(Integer)
    mae: Mapped[float] = mapped_column(Float)
    mse: Mapped[float] = mapped_column(Float)
    rmse: Mapped[float] = mapped_column(Float)
    mape: Mapped[float] = mapped_column(Float)
    r2: Mapped[float] = mapped_column(Float)
    interval_coverage: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (
        UniqueConstraint("model_version_id", "scope"),
        CheckConstraint("scope IN ('cv_dev','test','baseline_test')", name="scope"),
        {"schema": MA},
    )


class EvaluationPrediction(Identity, Base):
    __tablename__ = "evaluation_predictions"
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id", ondelete="CASCADE")
    )
    scope: Mapped[str] = mapped_column(String(20))
    # seed = dataset publik awal; actuals = data aktual restoran (tidak dibuka lewat API).
    source: Mapped[str] = mapped_column(String(10))
    observation_date: Mapped[date] = mapped_column(Date)
    fold: Mapped[int | None] = mapped_column(Integer)
    actual_kg: Mapped[float] = mapped_column(Float)
    predicted_kg: Mapped[float] = mapped_column(Float)
    error_kg: Mapped[float] = mapped_column(Float)
    __table_args__ = (
        CheckConstraint("scope IN ('oof_dev','test')", name="scope"),
        CheckConstraint("source IN ('seed','actuals')", name="source"),
        Index(
            "ix_evaluation_predictions_version_scope_date",
            "model_version_id",
            "scope",
            "observation_date",
        ),
        {"schema": MA},
    )


class FeatureImportance(Identity, Base):
    __tablename__ = "feature_importances"
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id", ondelete="CASCADE")
    )
    feature: Mapped[str] = mapped_column(String(80))
    importance_mae: Mapped[float] = mapped_column(Float)
    importance_std: Mapped[float] = mapped_column(Float)
    rank: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("model_version_id", "feature"), {"schema": MA})


class SensitivityCurve(Identity, Base):
    __tablename__ = "sensitivity_curves"
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id", ondelete="CASCADE")
    )
    staff_experience: Mapped[str] = mapped_column(String(20))
    special_event: Mapped[bool] = mapped_column(Boolean)
    meals_prepared: Mapped[int] = mapped_column(Integer)
    predicted_kg: Mapped[float] = mapped_column(Float)
    within_training_range: Mapped[bool] = mapped_column(Boolean)
    __table_args__ = (
        UniqueConstraint(
            "model_version_id", "staff_experience", "special_event", "meals_prepared"
        ),
        {"schema": MA},
    )


class EvaluationReport(Identity, Base):
    __tablename__ = "evaluation_reports"
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id", ondelete="CASCADE")
    )
    file_format: Mapped[str] = mapped_column(String(10))
    storage_path: Mapped[str] = mapped_column(String(500))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        UniqueConstraint("model_version_id", "file_format"),
        CheckConstraint("file_format IN ('xlsx','pdf')", name="format"),
        {"schema": MA},
    )
