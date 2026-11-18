"""Kontrak JSON frontend dan validasi sebelum data masuk PostgreSQL."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class Credentials(Input):
    email: str = Field(min_length=3, max_length=254, pattern=EMAIL)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value):
        return value.lower()


class Register(Credentials):
    name: str = Field(min_length=2, max_length=120)
    restaurant_name: str = Field(min_length=2, max_length=160)


class UserCreate(Credentials):
    name: str = Field(min_length=2, max_length=120)
    role: Literal["manager", "staff"] = "manager"


class ProfileUpdate(Input):
    name: str = Field(min_length=2, max_length=120)
    notification_preferences: dict[str, bool] = Field(default_factory=dict)


class RestaurantUpdate(Input):
    name: str = Field(min_length=2, max_length=160)


class SettingsUpdate(Input):
    ingredient_cost_per_kg: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    safe_max_kg: Decimal = Field(ge=0, max_digits=12, decimal_places=4)
    warning_max_kg: Decimal = Field(gt=0, max_digits=12, decimal_places=4)
    max_portions: int = Field(gt=0, le=1_000_000)
    reduction_target_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    high_risk_notifications: bool = True
    report_recipient_email: str | None = Field(default=None, max_length=254, pattern=EMAIL)

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if self.warning_max_kg <= self.safe_max_kg:
            raise ValueError("Batas Waspada harus lebih besar daripada batas Aman.")
        return self


class DailyInput(Input):
    operation_date: date
    meals_prepared: int = Field(ge=0, le=1_000_000)
    kitchen_staff: int = Field(gt=0, le=10_000)
    staff_experience: Literal["beginner", "intermediate", "expert"]
    special_event: bool = False
    event_type: str | None = Field(default=None, max_length=120)
    temperature_c: Decimal = Field(ge=-50, le=100, max_digits=7, decimal_places=2)
    humidity_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    previous_waste_kg: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    waste_category: str | None = Field(default=None, max_length=80)
    actual_waste_kg: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    manager_notes: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def event_is_consistent(self):
        if not self.special_event and self.event_type:
            raise ValueError("Jenis acara hanya diisi ketika acara khusus aktif.")
        return self


class DailyUpdate(DailyInput):
    expected_version: int = Field(ge=1)
    correction_reason: str = Field(min_length=3, max_length=500)


class PredictionPreview(Input):
    """Isian rencana untuk pratinjau prediksi tanpa menyimpan apa pun."""

    operation_date: date
    meals_prepared: int = Field(ge=0, le=1_000_000)
    kitchen_staff: int = Field(gt=0, le=10_000)
    staff_experience: Literal["beginner", "intermediate", "expert"]
    special_event: bool = False
    temperature_c: Decimal = Field(ge=-50, le=100, max_digits=7, decimal_places=2)
    humidity_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class WeeklyCreate(Input):
    title: str = Field(min_length=2, max_length=160)
    starts_on: date
    days: list[DailyInput] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def dates_are_consecutive(self):
        expected = {self.starts_on.fromordinal(self.starts_on.toordinal() + i) for i in range(7)}
        if {day.operation_date for day in self.days} != expected:
            raise ValueError("Isi tujuh tanggal berbeda berurutan mulai starts_on.")
        return self


class PlanDayUpdate(DailyUpdate):
    pass


REDUCTIONS = (0, 5, 10, 15)


class ScenarioCreate(Input):
    daily_operation_id: UUID
    reduction_percent: Literal[0, 5, 10, 15] = 0
    kitchen_staff: int | None = Field(default=None, gt=0, le=10_000)
    application_date: date
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "saved"] = "draft"


class ScenarioOptions(Input):
    daily_operation_id: UUID
    kitchen_staff: int | None = Field(default=None, gt=0, le=10_000)


class ApplyScenario(Input):
    expected_operation_version: int = Field(ge=1)


class ReportRequest(Input):
    starts_on: date
    ends_on: date
    period_type: Literal["weekly", "monthly", "custom"] = "custom"
    waste_category: str | None = Field(default=None, max_length=80)
    search: str | None = Field(default=None, max_length=200)
    sort_order: Literal["date_asc", "date_desc", "waste_asc", "waste_desc"] = "date_desc"
    file_format: Literal["pdf", "xlsx"]
    email_recipient: str | None = Field(default=None, max_length=254, pattern=EMAIL)
    email_subject: str | None = Field(default=None, max_length=200, pattern=r"^[^\r\n]*$")
    email_message: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def valid_period(self):
        if self.ends_on < self.starts_on:
            raise ValueError("Tanggal akhir tidak boleh sebelum tanggal mulai.")
        if (self.ends_on - self.starts_on).days > 366:
            raise ValueError("Maksimal satu tahun per laporan.")
        return self
