"""Tabel PostgreSQL untuk data restoran, input, dan jejak prediksi.

JSONB menyimpan snapshot/audit yang bentuknya bisa berubah. Nilai operasional
utama tetap berupa kolom bertipe, sehingga dapat difilter dan dijumlahkan SQL.
"""

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
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from api.database import Base

JSON_DATA = JSON().with_variant(JSONB(), "postgresql")
MONEY = Numeric(18, 2)
KG = Numeric(12, 4)


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Tenant(Identity):
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), index=True
    )


class Restaurant(Identity, Base):
    __tablename__ = "restaurants"
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(60), default="Asia/Jakarta")
    currency: Mapped[str] = mapped_column(String(3), default="IDR")


class User(Tenant, Base):
    __tablename__ = "users"
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="manager")
    status: Mapped[str] = mapped_column(String(20), default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notification_preferences: Mapped[dict] = mapped_column(JSON_DATA, default=dict)
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        CheckConstraint("role IN ('owner','manager','staff')", name="ck_users_role"),
        CheckConstraint("status IN ('active','inactive')", name="ck_users_status"),
    )


class UserSession(Tenant, Base):
    __tablename__ = "user_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "user_id"], ["users.restaurant_id", "users.id"], ondelete="CASCADE"
        ),
    )


class RestaurantSettings(Base):
    __tablename__ = "restaurant_settings"
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), primary_key=True
    )
    ingredient_cost_per_kg: Mapped[Decimal] = mapped_column(MONEY, default=0)
    safe_max_kg: Mapped[Decimal] = mapped_column(KG, default=35)
    warning_max_kg: Mapped[Decimal] = mapped_column(KG, default=47)
    max_portions: Mapped[int] = mapped_column(Integer, default=5000)
    reduction_target_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=10)
    high_risk_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    report_recipient_email: Mapped[str | None] = mapped_column(String(254))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "ingredient_cost_per_kg >= 0 AND safe_max_kg >= 0 AND warning_max_kg > safe_max_kg AND max_portions > 0 AND reduction_target_percent BETWEEN 0 AND 100",
            name="ck_settings_values",
        ),
    )


class DataImport(Tenant, Base):
    __tablename__ = "data_imports"
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    storage_key: Mapped[str | None] = mapped_column(String(100))
    file_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="validated")
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0)
    unusual_rows: Mapped[int] = mapped_column(Integer, default=0)
    applied_rows: Mapped[int] = mapped_column(Integer, default=0)
    validation_results: Mapped[list] = mapped_column(JSON_DATA, default=list)
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        CheckConstraint("status IN ('validated','applied','rejected')", name="ck_import_status"),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0 AND valid_rows + invalid_rows = total_rows AND unusual_rows BETWEEN 0 AND valid_rows AND applied_rows BETWEEN 0 AND valid_rows",
            name="ck_import_counts",
        ),
    )


class DailyOperation(Tenant, Base):
    __tablename__ = "daily_operations"
    operation_date: Mapped[date] = mapped_column(Date)
    meals_prepared: Mapped[int] = mapped_column(Integer)
    kitchen_staff: Mapped[int] = mapped_column(Integer)
    staff_experience: Mapped[str] = mapped_column(String(20))
    special_event: Mapped[bool] = mapped_column(Boolean, default=False)
    event_type: Mapped[str | None] = mapped_column(String(120))
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    humidity_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    previous_waste_kg: Mapped[Decimal | None] = mapped_column(KG)
    waste_category: Mapped[str | None] = mapped_column(String(80))
    actual_waste_kg: Mapped[Decimal | None] = mapped_column(KG)
    manager_notes: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    import_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        UniqueConstraint("restaurant_id", "operation_date", name="uq_daily_restaurant_date"),
        UniqueConstraint("restaurant_id", "id"),
        ForeignKeyConstraint(
            ["restaurant_id", "import_id"], ["data_imports.restaurant_id", "data_imports.id"]
        ),
        CheckConstraint(
            "meals_prepared >= 0 AND kitchen_staff > 0 AND humidity_percent BETWEEN 0 AND 100 AND (actual_waste_kg IS NULL OR actual_waste_kg >= 0) AND (previous_waste_kg IS NULL OR previous_waste_kg >= 0)",
            name="ck_daily_values",
        ),
        CheckConstraint(
            "staff_experience IN ('beginner','intermediate','expert')", name="ck_daily_experience"
        ),
    )


class DataCorrection(Tenant, Base):
    __tablename__ = "data_corrections"
    daily_operation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    previous_values: Mapped[dict] = mapped_column(JSON_DATA)
    new_values: Mapped[dict] = mapped_column(JSON_DATA)
    previous_version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            ["daily_operations.restaurant_id", "daily_operations.id"],
        ),
    )


class ModelVersion(Identity, Base):
    __tablename__ = "model_versions"
    version_key: Mapped[str] = mapped_column(String(160), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    preprocessing: Mapped[str] = mapped_column(String(40))
    artifact_path: Mapped[str] = mapped_column(String(500))
    preprocessing_path: Mapped[str] = mapped_column(String(500))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    preprocessing_sha256: Mapped[str] = mapped_column(String(64))
    metrics: Mapped[dict] = mapped_column(JSON_DATA)
    input_features: Mapped[list] = mapped_column(JSON_DATA)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        Index(
            "uq_model_versions_active", "is_active", unique=True, postgresql_where=text("is_active")
        ),
    )


class WeeklyPrediction(Tenant, Base):
    __tablename__ = "weekly_predictions"
    starts_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(160))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        CheckConstraint("status IN ('draft','saved')", name="ck_weekly_status"),
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
            ["weekly_predictions.restaurant_id", "weekly_predictions.id"],
            ondelete="CASCADE",
        ),
    )


class PlanRevision(Tenant, Base):
    __tablename__ = "plan_revisions"
    prediction_day_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    previous_input: Mapped[dict] = mapped_column(JSON_DATA)
    new_input: Mapped[dict] = mapped_column(JSON_DATA)
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_day_id"],
            ["prediction_days.restaurant_id", "prediction_days.id"],
        ),
    )


class PredictionResult(Tenant, Base):
    __tablename__ = "prediction_results"
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    daily_operation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    prediction_day_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation_version: Mapped[int | None] = mapped_column(Integer)
    predicted_waste_kg: Mapped[Decimal] = mapped_column(KG)
    interval_lower_kg: Mapped[Decimal] = mapped_column(KG)
    interval_upper_kg: Mapped[Decimal] = mapped_column(KG)
    risk_level: Mapped[str] = mapped_column(String(20))
    recommended_portions: Mapped[int | None] = mapped_column(Integer)
    portions_per_staff: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    estimated_waste_cost: Mapped[Decimal] = mapped_column(MONEY)
    potential_savings_kg: Mapped[Decimal | None] = mapped_column(KG)
    potential_savings_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    input_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    settings_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    explanation: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            ["daily_operations.restaurant_id", "daily_operations.id"],
        ),
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_day_id"],
            ["prediction_days.restaurant_id", "prediction_days.id"],
        ),
        CheckConstraint(
            "(daily_operation_id IS NOT NULL AND prediction_day_id IS NULL) OR (daily_operation_id IS NULL AND prediction_day_id IS NOT NULL)",
            name="ck_prediction_parent",
        ),
        CheckConstraint(
            "predicted_waste_kg >= 0 AND interval_lower_kg >= 0 AND interval_upper_kg >= interval_lower_kg",
            name="ck_prediction_values",
        ),
        CheckConstraint("risk_level IN ('safe','warning','high')", name="ck_prediction_risk"),
        Index("ix_predictions_restaurant_created", "restaurant_id", "created_at"),
    )


class PortionScenario(Tenant, Base):
    __tablename__ = "portion_scenarios"
    daily_operation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    model_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("model_versions.id"))
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
    shortage_risk: Mapped[str] = mapped_column(String(20), default="unknown")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    input_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    settings_snapshot: Mapped[dict] = mapped_column(JSON_DATA)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            ["daily_operations.restaurant_id", "daily_operations.id"],
        ),
        CheckConstraint("status IN ('draft','saved','applied')", name="ck_scenario_status"),
        CheckConstraint(
            "baseline_portions >= 0 AND simulated_portions >= 0 AND kitchen_staff > 0 AND reduction_percent BETWEEN 0 AND 100",
            name="ck_scenario_values",
        ),
    )


class OperationalInsight(Tenant, Base):
    __tablename__ = "operational_insights"
    # Nullable hanya untuk insight lama yang pembuatnya tidak tercatat.
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    daily_operation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200))
    impact_kg: Mapped[Decimal | None] = mapped_column(KG)
    impact_amount: Mapped[Decimal | None] = mapped_column(MONEY)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    suggested_action: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="new")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            ["daily_operations.restaurant_id", "daily_operations.id"],
        ),
        CheckConstraint("status IN ('new','reviewed','applied')", name="ck_insight_status"),
        CheckConstraint("priority IN ('low','medium','high')", name="ck_insight_priority"),
    )


class DailyTask(Tenant, Base):
    __tablename__ = "daily_tasks"
    task_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class Notification(Tenant, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    prediction_result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(["restaurant_id", "user_id"], ["users.restaurant_id", "users.id"]),
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_result_id"],
            ["prediction_results.restaurant_id", "prediction_results.id"],
        ),
    )


class ReportExport(Tenant, Base):
    __tablename__ = "report_exports"
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    period_type: Mapped[str] = mapped_column(String(20))
    waste_category: Mapped[str | None] = mapped_column(String(80))
    search: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[str] = mapped_column(String(20), default="date_desc")
    file_format: Mapped[str] = mapped_column(String(10))
    file_name: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(String(100))
    generation_status: Mapped[str] = mapped_column(String(20), default="requested")
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_recipient: Mapped[str | None] = mapped_column(String(254))
    email_subject: Mapped[str | None] = mapped_column(String(200))
    email_message: Mapped[str | None] = mapped_column(Text)
    email_status: Mapped[str] = mapped_column(String(20), default="not_requested")
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id", name="uq_report_restaurant_id"),
        CheckConstraint("ends_on >= starts_on", name="ck_report_dates"),
        CheckConstraint("file_format IN ('pdf','xlsx')", name="ck_report_format"),
        CheckConstraint(
            "generation_status IN ('requested','ready','failed')",
            name="ck_report_generation_status",
        ),
        CheckConstraint(
            "email_status IN ('not_requested','not_configured','pending','sent','failed')",
            name="ck_report_email_status",
        ),
        CheckConstraint(
            "generation_status != 'ready' OR (storage_key IS NOT NULL AND file_name IS NOT NULL)",
            name="ck_report_ready_file",
        ),
    )


class EmailDelivery(Tenant, Base):
    __tablename__ = "email_deliveries"
    report_export_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    transport: Mapped[str] = mapped_column(String(20), default="mailpit")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    message_id: Mapped[str] = mapped_column(String(160), unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    last_error: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint("restaurant_id", "id"),
        ForeignKeyConstraint(
            ["restaurant_id", "report_export_id"],
            ["report_exports.restaurant_id", "report_exports.id"],
        ),
        CheckConstraint(
            "status IN ('pending','sent','failed') AND transport = 'mailpit'",
            name="ck_delivery_status",
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts",
            name="ck_delivery_attempts",
        ),
    )


class EmailAttempt(Tenant, Base):
    __tablename__ = "email_attempts"
    email_delivery_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    attempt_number: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        UniqueConstraint("email_delivery_id", "attempt_number"),
        ForeignKeyConstraint(
            ["restaurant_id", "email_delivery_id"],
            ["email_deliveries.restaurant_id", "email_deliveries.id"],
        ),
        CheckConstraint("attempt_number > 0", name="ck_email_attempt_number"),
    )


# Manager yang menjadi actor juga harus berasal dari restoran yang sama.
# FK id tunggal tetap ada; FK komposit menambahkan perlindungan di tingkat DB.
for table in Base.metadata.tables.values():
    if "restaurant_id" not in table.c:
        continue
    for field in [
        "created_by",
        "updated_by",
        "changed_by",
        "reviewed_by",
        "completed_by",
        "applied_by",
    ]:
        if field in table.c:
            table.append_constraint(
                ForeignKeyConstraint(
                    ["restaurant_id", field],
                    ["users.restaurant_id", "users.id"],
                    name=f"fk_{table.name}_{field}_restaurant",
                )
            )
