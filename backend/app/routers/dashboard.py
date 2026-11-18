"""Halaman Dashboard: hanya membaca prediksi tersimpan dan data operasional."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser, Db
from app.models import (
    DailyOperation,
    ModelVersion,
    Notification,
    PortionScenario,
    PredictionResult,
)
from app.services.common import restaurant_settings, serialize

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def latest_prediction(db, user, operation):
    return db.scalar(
        select(PredictionResult)
        .where(
            PredictionResult.restaurant_id == user.restaurant_id,
            PredictionResult.daily_operation_id == operation.id,
        )
        .order_by(PredictionResult.created_at.desc(), PredictionResult.id.desc())
        .limit(1)
    )


@router.get("")
def dashboard(db: Db, user: CurrentUser, on: date):
    operation = db.scalar(
        select(DailyOperation).where(
            DailyOperation.restaurant_id == user.restaurant_id, DailyOperation.operation_date == on
        )
    )
    latest = latest_prediction(db, user, operation) if operation else None
    scenarios = db.scalars(
        select(PortionScenario).where(
            PortionScenario.restaurant_id == user.restaurant_id,
            PortionScenario.application_date == on,
            PortionScenario.status == "applied",
        )
    ).all()
    active = db.scalar(select(ModelVersion).where(ModelVersion.is_active.is_(True)))
    settings = restaurant_settings(db, user)
    return {
        "operation": serialize(operation) if operation else None,
        "prediction": serialize(latest) if latest else None,
        # True bila input diubah setelah prediksi terakhir: tampilkan tombol "Jalankan prediksi".
        "prediction_is_stale": bool(
            operation and (latest is None or latest.operation_version != operation.version)
        ),
        "applied_scenarios": [serialize(s) for s in scenarios],
        "unread_notifications": db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.restaurant_id == user.restaurant_id,
                Notification.user_id == user.id,
                Notification.read_at.is_(None),
            )
        ),
        "thresholds": {
            "safe_max_kg": settings.safe_max_kg,
            "warning_max_kg": settings.warning_max_kg,
        },
        "reduction_target_percent": settings.reduction_target_percent,
        "model": (
            {"version_key": active.version_key, "test_mae": active.metrics.get("test_mae")}
            if active
            else None
        ),
    }


@router.get("/trend")
def trend(db: Db, user: CurrentUser, end: date, days: int = Query(30, ge=7, le=180)):
    """Aktual vs prediksi tersimpan per tanggal, beserta MAE pasangan yang lengkap."""
    start = end - timedelta(days=days - 1)
    operations = db.scalars(
        select(DailyOperation)
        .where(
            DailyOperation.restaurant_id == user.restaurant_id,
            DailyOperation.operation_date.between(start, end),
        )
        .order_by(DailyOperation.operation_date)
    ).all()
    ids = [o.id for o in operations]
    latest = {}
    if ids:
        for result in db.scalars(
            select(PredictionResult)
            .where(
                PredictionResult.restaurant_id == user.restaurant_id,
                PredictionResult.daily_operation_id.in_(ids),
            )
            .order_by(PredictionResult.created_at.asc())
        ):
            latest[result.daily_operation_id] = result
    series, errors = [], []
    for op in operations:
        pred = latest.get(op.id)
        item = {
            "date": op.operation_date,
            "actual_waste_kg": op.actual_waste_kg,
            "predicted_waste_kg": pred.predicted_waste_kg if pred else None,
            "interval_lower_kg": pred.interval_lower_kg if pred else None,
            "interval_upper_kg": pred.interval_upper_kg if pred else None,
            "risk_level": pred.risk_level if pred else None,
        }
        if pred and op.actual_waste_kg is not None:
            errors.append(abs(op.actual_waste_kg - pred.predicted_waste_kg))
        series.append(item)
    return {
        "starts_on": start,
        "ends_on": end,
        "series": series,
        "paired_days": len(errors),
        "mae_kg": (sum(errors, Decimal(0)) / len(errors)).quantize(Decimal(".0001"))
        if errors
        else None,
    }
