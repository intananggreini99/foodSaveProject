"""Prediksi realtime untuk input harian, pratinjau, dan riwayat prediksi."""

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, Db, Manager
from app.models import DailyOperation, PredictionResult
from app.schemas import PredictionPreview
from app.services.common import daily_snapshot, owned, serialize
from app.services.predictions import calculate_prediction, preview

router = APIRouter(tags=["Prediksi realtime"])


@router.post("/predictions/preview")
def prediction_preview(body: PredictionPreview, db: Db, user: CurrentUser):
    """Pratinjau di form Input Data Harian. Tidak menyimpan prediksi."""
    result = preview(db, user, body.model_dump(mode="json"))
    db.commit()  # hanya menyimpan log inferensi
    return result


@router.post("/daily-operations/{operation_id}/predict", status_code=201)
def predict(operation_id: UUID, db: Db, user: Manager):
    operation = owned(db, DailyOperation, operation_id, user, lock=True)
    result = calculate_prediction(db, user, daily_snapshot(operation), daily=operation)
    db.commit()
    return serialize(result)


@router.get("/predictions")
def predictions(
    db: Db,
    user: CurrentUser,
    daily_operation_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(PredictionResult).where(PredictionResult.restaurant_id == user.restaurant_id)
    if daily_operation_id:
        query = query.where(PredictionResult.daily_operation_id == daily_operation_id)
    rows = db.scalars(
        query.order_by(PredictionResult.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return [serialize(row) for row in rows]


@router.get("/predictions/{prediction_id}")
def prediction(prediction_id: UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, PredictionResult, prediction_id, user))
