from uuid import UUID
from fastapi import APIRouter, Query
from sqlalchemy import select
from api.auth import CurrentUser, Db, Manager
from api.models import DailyOperation, ModelVersion, PredictionResult
from api.services import calculate_prediction, daily_snapshot, owned, serialize

router = APIRouter(tags=["Prediksi dan versi model"])


@router.get("/models")
def models(db: Db, user: CurrentUser):
    return [
        serialize(row, exclude={"artifact_path", "preprocessing_path"})
        for row in db.scalars(select(ModelVersion).order_by(ModelVersion.created_at.desc())).all()
    ]


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
    return [
        serialize(row)
        for row in db.scalars(
            query.order_by(PredictionResult.created_at.desc()).limit(limit).offset(offset)
        ).all()
    ]


@router.get("/predictions/{prediction_id}")
def prediction(prediction_id: UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, PredictionResult, prediction_id, user))
