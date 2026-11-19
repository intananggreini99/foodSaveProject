"""Kontrak JSON API dan validasi sebelum data masuk PostgreSQL.

Contoh di "examples" tampil sebagai body awal di Swagger UI (/docs) dan valid apa adanya,
kecuali id yang harus diganti dengan id dari respons sebelumnya.
"""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

EMAIL = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


def example(**values):
    """Body contoh untuk Swagger UI."""
    return ConfigDict(json_schema_extra={"examples": [values]})


DAY = {
    "operation_date": "2026-11-19",
    "meals_prepared": 400,
    "kitchen_staff": 12,
    "staff_experience": "intermediate",
    "special_event": False,
    "event_type": None,
    "temperature_c": 28,
    "humidity_percent": 65,
    "previous_waste_kg": 20,
    "waste_category": "vegetables",
    "actual_waste_kg": None,
    "manager_notes": "Rencana makan siang biasa",
}
WEEK = [
    {**DAY, "operation_date": f"2026-11-{23 + i:02d}", "meals_prepared": meals,
     "special_event": event, "event_type": "Katering kantor" if event else None,
     "previous_waste_kg": None, "waste_category": None, "manager_notes": None}
    for i, (meals, event) in enumerate(
        [(380, False), (400, False), (420, False), (410, False), (520, True), (600, True), (350, False)]
    )
]
ANY_ID = "00000000-0000-0000-0000-000000000000"


class Credentials(Input):
    model_config = example(email="pemilik@contoh.test", password="rahasiaPanjang123")

    email: str = Field(min_length=3, max_length=254, pattern=EMAIL)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value):
        return value.lower()


class Register(Credentials):
    model_config = example(
        email="pemilik@contoh.test",
        password="rahasiaPanjang123",
        name="Ani Wulandari",
        restaurant_name="Warung Makan Sederhana",
    )

    name: str = Field(min_length=2, max_length=120)
    restaurant_name: str = Field(min_length=2, max_length=160)


class UserCreate(Credentials):
    model_config = example(
        email="staf@contoh.test", password="rahasiaPanjang123", name="Budi Santoso", role="staff"
    )

    name: str = Field(min_length=2, max_length=120)
    role: Literal["manager", "staff"] = "manager"


class ProfileUpdate(Input):
    model_config = example(name="Ani Wulandari", notification_preferences={"high_risk": True})

    name: str = Field(min_length=2, max_length=120)
    notification_preferences: dict[str, bool] = Field(default_factory=dict)


class RestaurantUpdate(Input):
    model_config = example(name="Warung Makan Sederhana Cabang Utama")

    name: str = Field(min_length=2, max_length=160)


class SettingsUpdate(Input):
    model_config = example(
        ingredient_cost_per_kg=25000,
        safe_max_kg=35.6,
        warning_max_kg=46.7,
        max_portions=5000,
        reduction_target_percent=10,
        high_risk_notifications=True,
        report_recipient_email="manager@contoh.test",
    )

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
    model_config = example(**DAY)

    operation_date: date = Field(description="Tanggal operasional (YYYY-MM-DD), satu input per tanggal.")
    meals_prepared: int = Field(ge=0, le=1_000_000, description="Porsi yang disiapkan.")
    kitchen_staff: int = Field(gt=0, le=10_000, description="Jumlah staf dapur.")
    staff_experience: Literal["beginner", "intermediate", "expert"] = Field(
        description="Pengalaman staf: beginner (pemula), intermediate (menengah), expert (ahli)."
    )
    special_event: bool = Field(default=False, description="Ada acara khusus.")
    event_type: str | None = Field(
        default=None, max_length=120, description="Jenis acara; hanya bila special_event true."
    )
    temperature_c: Decimal = Field(ge=-50, le=100, max_digits=7, decimal_places=2, description="Suhu (°C).")
    humidity_percent: Decimal = Field(
        ge=0, le=100, max_digits=5, decimal_places=2, description="Kelembapan (%)."
    )
    previous_waste_kg: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4,
        description="Limbah periode sebelumnya (kg); disimpan, tidak dipakai model.",
    )
    waste_category: str | None = Field(
        default=None, max_length=80,
        description="Kategori limbah: vegetables, meat, grains, dairy; tidak dipakai model.",
    )
    actual_waste_kg: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=4,
        description="Limbah aktual hasil timbang (kg); kosongkan (null) bila belum ditimbang.",
    )
    manager_notes: str | None = Field(default=None, max_length=4000, description="Catatan manager.")

    @model_validator(mode="after")
    def event_is_consistent(self):
        if not self.special_event and self.event_type:
            raise ValueError("Jenis acara hanya diisi ketika acara khusus aktif.")
        return self


class DailyUpdate(DailyInput):
    model_config = example(
        **{**DAY, "actual_waste_kg": 27.5},
        expected_version=1,
        correction_reason="Penimbangan limbah aktual sudah selesai",
    )

    expected_version: int = Field(ge=1, description="Isi dengan version dari respons terakhir.")
    correction_reason: str = Field(min_length=3, max_length=500, description="Alasan koreksi.")


class PredictionPreview(Input):
    """Isian rencana untuk pratinjau prediksi tanpa menyimpan apa pun."""

    model_config = example(
        operation_date="2026-11-19",
        meals_prepared=400,
        kitchen_staff=12,
        staff_experience="intermediate",
        special_event=False,
        temperature_c=28,
        humidity_percent=65,
    )

    operation_date: date
    meals_prepared: int = Field(ge=0, le=1_000_000)
    kitchen_staff: int = Field(gt=0, le=10_000)
    staff_experience: Literal["beginner", "intermediate", "expert"]
    special_event: bool = False
    temperature_c: Decimal = Field(ge=-50, le=100, max_digits=7, decimal_places=2)
    humidity_percent: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)


class WeeklyCreate(Input):
    model_config = example(title="Rencana 23 sampai 29 Nov", starts_on="2026-11-23", days=WEEK)

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
    model_config = example(
        **{**WEEK[5], "meals_prepared": 450},
        expected_version=1,
        correction_reason="Pesanan katering berkurang",
    )


REDUCTIONS = (0, 5, 10, 15)


class ScenarioCreate(Input):
    model_config = example(
        daily_operation_id=ANY_ID,
        reduction_percent=10,
        kitchen_staff=None,
        application_date="2026-11-19",
        notes="Uji pengurangan 10%",
        status="saved",
    )

    daily_operation_id: UUID
    reduction_percent: Literal[0, 5, 10, 15] = 0
    kitchen_staff: int | None = Field(default=None, gt=0, le=10_000)
    application_date: date
    notes: str | None = Field(default=None, max_length=4000)
    status: Literal["draft", "saved"] = "draft"


class ScenarioOptions(Input):
    model_config = example(daily_operation_id=ANY_ID, kitchen_staff=None)

    daily_operation_id: UUID
    kitchen_staff: int | None = Field(default=None, gt=0, le=10_000)


class ApplyScenario(Input):
    model_config = example(expected_operation_version=1)

    expected_operation_version: int = Field(ge=1)


class ReportRequest(Input):
    model_config = example(
        starts_on="2026-11-01",
        ends_on="2026-11-30",
        period_type="monthly",
        waste_category=None,
        search=None,
        sort_order="date_desc",
        file_format="pdf",
        email_recipient="manager@contoh.test",
        email_subject="Laporan FoodSave November 2026",
        email_message="Mohon tinjau laporan pada lampiran.",
    )

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
