"""Skema operational: akun, restoran, input harian, laporan, notifikasi, ekspor data."""

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
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.common import JSON_DATA, KG, MONEY, OP, PRED, Identity, Tenant


class Restaurant(Identity, Base):
    __tablename__ = "restaurants"
    __table_args__ = {"schema": OP}
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
        CheckConstraint("role IN ('owner','manager','staff')", name="role"),
        CheckConstraint("status IN ('active','disabled')", name="status"),
        {"schema": OP},
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
            ["restaurant_id", "user_id"], [f"{OP}.users.restaurant_id", f"{OP}.users.id"]
        ),
        {"schema": OP},
    )


class RestaurantSettings(Base):
    __tablename__ = "restaurant_settings"
    restaurant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(f"{OP}.restaurants.id", ondelete="CASCADE"), primary_key=True
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
            "ingredient_cost_per_kg >= 0 AND safe_max_kg >= 0 AND warning_max_kg > safe_max_kg"
            " AND max_portions > 0 AND reduction_target_percent BETWEEN 0 AND 100",
            name="values",
        ),
        {"schema": OP},
    )


class DataImport(Tenant, Base):
    __tablename__ = "data_imports"
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
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
        CheckConstraint("status IN ('validated','applied','rejected')", name="status"),
        CheckConstraint(
            "total_rows >= 0 AND valid_rows >= 0 AND invalid_rows >= 0"
            " AND valid_rows + invalid_rows = total_rows"
            " AND unusual_rows BETWEEN 0 AND valid_rows AND applied_rows BETWEEN 0 AND valid_rows",
            name="counts",
        ),
        {"schema": OP},
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
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    updated_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
    __mapper_args__ = {"version_id_col": version}
    __table_args__ = (
        UniqueConstraint("restaurant_id", "operation_date"),
        UniqueConstraint("restaurant_id", "id"),
        ForeignKeyConstraint(
            ["restaurant_id", "import_id"],
            [f"{OP}.data_imports.restaurant_id", f"{OP}.data_imports.id"],
        ),
        CheckConstraint(
            "meals_prepared >= 0 AND kitchen_staff > 0 AND humidity_percent BETWEEN 0 AND 100"
            " AND (actual_waste_kg IS NULL OR actual_waste_kg >= 0)"
            " AND (previous_waste_kg IS NULL OR previous_waste_kg >= 0)",
            name="values",
        ),
        CheckConstraint(
            "staff_experience IN ('beginner','intermediate','expert')", name="experience"
        ),
        CheckConstraint("source IN ('manual','import')", name="source"),
        {"schema": OP},
    )


class DataCorrection(Tenant, Base):
    __tablename__ = "data_corrections"
    daily_operation_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    changed_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    previous_values: Mapped[dict] = mapped_column(JSON_DATA)
    new_values: Mapped[dict] = mapped_column(JSON_DATA)
    previous_version: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "daily_operation_id"],
            [f"{OP}.daily_operations.restaurant_id", f"{OP}.daily_operations.id"],
        ),
        {"schema": OP},
    )


class Notification(Tenant, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    prediction_result_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(
            ["restaurant_id", "user_id"], [f"{OP}.users.restaurant_id", f"{OP}.users.id"]
        ),
        # Lintas skema: notifikasi menunjuk hasil prediksi yang memicunya.
        ForeignKeyConstraint(
            ["restaurant_id", "prediction_result_id"],
            [f"{PRED}.prediction_results.restaurant_id", f"{PRED}.prediction_results.id"],
        ),
        {"schema": OP},
    )


class ReportExport(Tenant, Base):
    __tablename__ = "report_exports"
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
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
        UniqueConstraint("restaurant_id", "id"),
        CheckConstraint("ends_on >= starts_on", name="dates"),
        CheckConstraint("file_format IN ('pdf','xlsx')", name="format"),
        CheckConstraint(
            "generation_status IN ('requested','ready','failed')", name="generation_status"
        ),
        CheckConstraint(
            "email_status IN ('not_requested','not_configured','pending','sent','failed')",
            name="email_status",
        ),
        CheckConstraint(
            "generation_status != 'ready' OR (storage_key IS NOT NULL AND file_name IS NOT NULL)",
            name="ready_file",
        ),
        {"schema": OP},
    )


class EmailDelivery(Tenant, Base):
    __tablename__ = "email_deliveries"
    report_export_id: Mapped[uuid.UUID] = mapped_column(Uuid, unique=True)
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey(f"{OP}.users.id"))
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
            [f"{OP}.report_exports.restaurant_id", f"{OP}.report_exports.id"],
        ),
        CheckConstraint(
            "status IN ('pending','sent','failed') AND transport = 'mailpit'", name="status"
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts > 0 AND attempts <= max_attempts", name="attempts"
        ),
        {"schema": OP},
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
            [f"{OP}.email_deliveries.restaurant_id", f"{OP}.email_deliveries.id"],
        ),
        CheckConstraint("attempt_number > 0", name="attempt_number"),
        {"schema": OP},
    )


class TrainingExport(Identity, Base):
    """Catatan ekspor data aktual ke HDFS /foodsave/raw/actuals untuk pelatihan ulang.

    Bukan milik satu restoran: satu file ekspor memuat data aktual semua restoran.
    """

    __tablename__ = "training_exports"
    triggered_by: Mapped[str] = mapped_column(String(20), default="schedule")
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(f"{OP}.users.id"))
    changed_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    changed_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    restaurant_count: Mapped[int] = mapped_column(Integer, default=0)
    first_operation_date: Mapped[date | None] = mapped_column(Date)
    last_operation_date: Mapped[date | None] = mapped_column(Date)
    storage_path: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(String(500))
    __table_args__ = (
        CheckConstraint("triggered_by IN ('schedule','manual')", name="trigger"),
        CheckConstraint("status IN ('completed','empty','failed')", name="status"),
        CheckConstraint(
            "status != 'completed' OR (storage_path IS NOT NULL AND sha256 IS NOT NULL"
            " AND row_count > 0)",
            name="completed_file",
        ),
        {"schema": OP},
    )
