"""Mengubah angka model menjadi hasil prediksi untuk restoran: rentang, risiko, biaya."""

from decimal import Decimal

from sqlalchemy import select

from app.models import Notification, PredictionResult, User
from app.schemas import DailyInput
from app.services.common import ensure_capacity, restaurant_settings, serialize
from app.services.prediction_service import prediction_service

EXPLANATION = (
    "Prediksi memakai tujuh isian rencana: tanggal, porsi, staf, pengalaman staf, acara khusus, "
    "suhu, dan kelembapan. Kategori limbah dan limbah sebelumnya tidak dipakai model. "
    "Rentang adalah ±{radius} kg (90% error validasi), bukan jaminan."
)


def risk_level(value: Decimal, settings) -> str:
    if value <= settings.safe_max_kg:
        return "safe"
    return "warning" if value <= settings.warning_max_kg else "high"


def describe(value: Decimal, active, settings, snapshot: dict) -> dict:
    radius = active.interval_radius
    flagged = prediction_service.outside_training_range(active, snapshot)
    meals, staff = int(snapshot["meals_prepared"]), int(snapshot["kitchen_staff"])
    return {
        "predicted_waste_kg": value,
        "interval_lower_kg": max(Decimal(0), value - radius).quantize(Decimal(".0001")),
        "interval_upper_kg": (value + radius).quantize(Decimal(".0001")),
        "risk_level": risk_level(value, settings),
        "portions_per_staff": (Decimal(meals) / staff).quantize(Decimal(".0001")),
        "estimated_waste_cost": (value * settings.ingredient_cost_per_kg).quantize(Decimal(".01")),
        "outside_training_range": bool(flagged),
        "outside_fields": flagged,
        "model_version": active.version_key,
    }


def preview(db, user, snapshot: dict) -> dict:
    """Pratinjau saat user mengetik: tidak menyimpan prediksi, hanya log inferensi."""
    settings = restaurant_settings(db, user)
    ensure_capacity(DailyInput.model_validate({**snapshot}), settings)
    active, (value,) = prediction_service.predict(db, [snapshot], user=user, source="preview")
    return describe(value, active, settings, snapshot)


def calculate_prediction(db, user, snapshot: dict, daily=None, plan_day=None, source="daily"):
    """Prediksi satu input harian atau satu hari rencana, lalu simpan hasilnya."""
    return calculate_many(db, user, [(snapshot, daily, plan_day)], source=source)[0]


def calculate_many(db, user, items, source: str):
    """Beberapa baris sekaligus (rencana 7 hari) dalam satu panggilan model."""
    settings = restaurant_settings(db, user)
    for snapshot, _, _ in items:
        ensure_capacity(DailyInput.model_validate(snapshot), settings)
    active, values = prediction_service.predict(
        db, [snapshot for snapshot, _, _ in items], user=user, source=source
    )
    settings_snapshot = serialize(settings)
    results = []
    for (snapshot, daily, plan_day), value in zip(items, values):
        info = describe(value, active, settings, snapshot)
        result = PredictionResult(
            restaurant_id=user.restaurant_id,
            created_by=user.id,
            model_version_id=active.version_id,
            daily_operation_id=daily.id if daily else None,
            prediction_day_id=plan_day.id if plan_day else None,
            operation_version=daily.version if daily else plan_day.version,
            predicted_waste_kg=info["predicted_waste_kg"],
            interval_lower_kg=info["interval_lower_kg"],
            interval_upper_kg=info["interval_upper_kg"],
            risk_level=info["risk_level"],
            portions_per_staff=info["portions_per_staff"],
            estimated_waste_cost=info["estimated_waste_cost"],
            outside_training_range=info["outside_training_range"],
            input_snapshot=snapshot,
            settings_snapshot=settings_snapshot,
            explanation=EXPLANATION.format(radius=active.interval_radius.normalize()),
        )
        db.add(result)
        db.flush()
        if result.risk_level == "high" and settings.high_risk_notifications:
            notify_high_risk(db, user, result, snapshot)
        results.append(result)
    return results


def notify_high_risk(db, user, result, snapshot):
    recipients = db.scalars(
        select(User).where(User.restaurant_id == user.restaurant_id, User.status == "active")
    ).all()
    for recipient in recipients:
        if recipient.notification_preferences.get("high_risk", True):
            db.add(
                Notification(
                    restaurant_id=user.restaurant_id,
                    user_id=recipient.id,
                    prediction_result_id=result.id,
                    title="Prediksi limbah tinggi",
                    message=(
                        f"Rencana {snapshot['operation_date']} diperkirakan menghasilkan "
                        f"{result.predicted_waste_kg} kg limbah."
                    ),
                )
            )
