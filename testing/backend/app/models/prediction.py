"""Skema prediction: hasil prediksi realtime, rencana 7 hari, simulasi porsi, log inferensi."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import JSON_DATA, KG, MA, MONEY, OP, PRED, Tenant


class WeeklyPrediction(Tenant, Base):
    __tablename__ = "weekly_predictions"
    starts_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(160))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    status: Mapped[str] = mapped_column(String(20), default="saved")
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        CheckConstraint("status IN ('draft','saved')", name="status"),
        {"schema": PRED},
    )


class PredictionDay(Tenant, Base):
    __tablename__ = "prediction_days"
    weekly_prediction_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    prediction_date: Mapped[date] = mapped_column(Date)
    input_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    version: Mapped[int] = mapped_column(Integer, default=1)
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        UniqueConstraint("weekly_prediction_id", "prediction_date"),
        ForeignKeyConstraint(
            ["restaurant_id", "weekly_prediction_id"],
            [f"{PRED}.weekly_predictions.restaurant_id", f"{PRED}.weekly_predictions.id"],
            ondelete="CASCADE",
        ),
        {"schema": PRED},
    )


class PlanRevision(Tenant, Base):
    __tablename__ = "plan_revisions"
    prediction_day_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    previous_input: Mapped[dict] = mapped_column(JSON_DATA)
    new_input: Mapped[dict] = mapped_column(JSON_DATA)
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_day_id"],
            [f"{PRED}.prediction_days.restaurant_id", f"{PRED}.prediction_days.id"],
        ),
        {"schema": PRED},
    )


class PredictionResult(Tenant, Base):
    __tablename__ = "prediction_results"
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{MA}.model_versions.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    daily_operation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    prediction_day_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation_version: Mapped[int | None] = mapped_column(Integer)
    predicted_waste_kg: Mapped[Decimal] = mapped_column(KG)
    interval_lower_kg: Mapped[Decimal] = mapped_column(KG)
    interval_upper_kg: Mapped[Decimal] = mapped_column(KG)
    risk_level: Mapped[str] = mapped_column(String(20))
    portions_per_staff: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    estimated_waste_cost: Mapped[Decimal] = mapped_column(MONEY)
    outside_training_range: Mapped[bool] = mapped_column(Boolean, default=False)
    input_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    settings_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    explanation: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        # Lintas skema ke operational.daily_operations (restoran yang sama).
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            [f"{OP}.daily_operations.restaurant_id", f"{OP}.daily_operations.id"],
        ),
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_day_id"],
            [f"{PRED}.prediction_days.restaurant_id", f"{PRED}.prediction_days.id"],
        ),
        CheckConstraint(
            "(daily_operation_id IS NOT NULL AND prediction_day_id IS NULL)"
            " OR (daily_operation_id IS NULL AND prediction_day_id IS NOT NULL)",
            name="parent",
        ),
        CheckConstraint(
            "predicted_waste_kg >= 0 AND interval_lower_kg >= 0"
            " AND interval_upper_kg >= interval_lower_kg",
            name="values",
        ),
        CheckConstraint("risk_level IN ('safe','warning','high')", name="risk"),
        Index("ix_prediction_results_restaurant_created", "restaurant_id", "created_at"),
        {"schema": PRED},
    )


class PortionScenario(Tenant, Base):
    __tablename__ = "portion_scenarios"
    daily_operation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{MA}.model_versions.id"))
    operation_version: Mapped[int] = mapped_column(Integer)
    application_date: Mapped[date] = mapped_column(Date)
    baseline_portions: Mapped[int] = mapped_column(Integer)
    simulated_portions: Mapped[int] = mapped_column(Integer)
    kitchen_staff: Mapped[int] = mapped_column(Integer)
    reduction_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    predicted_waste_kg: Mapped[Decimal] = mapped_column(KG)
    baseline_waste_kg: Mapped[Decimal] = mapped_column(KG)
    savings_kg: Mapped[Decimal] = mapped_column(KG)
    savings_amount: Mapped[Decimal] = mapped_column(MONEY)
    portions_per_staff: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    settings_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{OP}.users.id"))
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            [f"{OP}.daily_operations.restaurant_id", f"{OP}.daily_operations.id"],
        ),
        CheckConstraint("status IN ('draft','saved','applied')", name="status"),
        CheckConstraint(
            "baseline_portions >= 0 AND simulated_portions >= 0 AND kitchen_staff > 0"
            " AND reduction_percent BETWEEN 0 AND 100",
            name="values",
        ),
        {"schema": PRED},
    )


class InferenceLog(Tenant, Base):
    """Satu baris per panggilan layanan prediksi (berhasil atau gagal)."""

    __tablename__ = "inference_logs"
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{OP}.users.id"))
    model_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(f"{MA}.model_versions.id")
    )
    source: Mapped[str] = mapped_column(String(20))
    row_count: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    success: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(String(300))
    __table_args__ = (
        CheckConstraint(
            "source IN ('daily','weekly','scenario','preview')", name="source"
        ),
        CheckConstraint("row_count >= 0 AND duration_ms >= 0", name="values"),
        Index("ix_inference_logs_restaurant_created", "restaurant_id", "created_at"),
        {"schema": PRED},
    )
