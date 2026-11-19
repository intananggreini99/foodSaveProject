"""Halaman Prediksi 7 Hari: tujuh prediksi realtime per rencana, ubah satu hari = 1 prediksi."""

from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from app.core.deps import CurrentUser, Db, Manager
from app.models import PlanRevision, PredictionDay, PredictionResult, WeeklyPrediction
from app.schemas import DailyInput, PlanDayUpdate, WeeklyCreate
from app.services.common import owned, serialize
from app.services.predictions import calculate_many, calculate_prediction

router = APIRouter(prefix="/weekly-predictions", tags=["Rencana tujuh hari"])


def detail(db, plan):
    days = db.scalars(
        select(PredictionDay)
        .where(
            PredictionDay.weekly_prediction_id == plan.id,
            PredictionDay.restaurant_id == plan.restaurant_id,
        )
        .order_by(PredictionDay.prediction_date)
    ).all()
    output = serialize(plan)
    output["days"] = []
    for day in days:
        item = serialize(day)
        latest = db.scalar(
            select(PredictionResult)
            .where(
                PredictionResult.prediction_day_id == day.id,
                PredictionResult.restaurant_id == plan.restaurant_id,
            )
            .order_by(PredictionResult.created_at.desc(), PredictionResult.id.desc())
        )
        item["prediction"] = serialize(latest) if latest else None
        output["days"].append(item)
    return output


@router.post("", status_code=201)
def create(body: WeeklyCreate, db: Db, user: Manager):
    plan = WeeklyPrediction(
        restaurant_id=user.restaurant_id,
        starts_on=body.starts_on,
        title=body.title,
        created_by=user.id,
        status="saved",
    )
    db.add(plan)
    db.flush()
    items = []
    for value in sorted(body.days, key=lambda d: d.operation_date):
        snapshot = value.model_dump(mode="json")
        day = PredictionDay(
            restaurant_id=user.restaurant_id,
            weekly_prediction_id=plan.id,
            prediction_date=value.operation_date,
            input_snapshot=snapshot,
        )
        db.add(day)
        db.flush()
        items.append((snapshot, None, day))
    # Tujuh hari diprediksi dalam satu panggilan model.
    calculate_many(db, user, items, source="weekly")
    db.commit()
    return detail(db, plan)


@router.get("")
def list_plans(
    db: Db, user: CurrentUser, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)
):
    return [
        serialize(row)
        for row in db.scalars(
            select(WeeklyPrediction)
            .where(WeeklyPrediction.restaurant_id == user.restaurant_id)
            .order_by(WeeklyPrediction.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    ]


@router.get("/{plan_id}")
def read(plan_id: UUID, db: Db, user: CurrentUser):
    return detail(db, owned(db, WeeklyPrediction, plan_id, user))


@router.put("/{plan_id}/days/{day_id}")
def update_day(plan_id: UUID, day_id: UUID, body: PlanDayUpdate, db: Db, user: Manager):
    plan = owned(db, WeeklyPrediction, plan_id, user)
    day = owned(db, PredictionDay, day_id, user, lock=True)
    if day.weekly_prediction_id != plan.id:
        raise HTTPException(404, "Hari tidak ditemukan dalam rencana ini.")
    if body.operation_date != day.prediction_date:
        raise HTTPException(422, "Tanggal hari rencana tidak dapat diganti.")
    if day.version != body.expected_version:
        raise HTTPException(409, "Rencana sudah berubah. Muat ulang terlebih dahulu.")
    snapshot = DailyInput.model_validate(
        body.model_dump(exclude={"expected_version", "correction_reason"})
    ).model_dump(mode="json")
    db.add(
        PlanRevision(
            restaurant_id=user.restaurant_id,
            prediction_day_id=day.id,
            changed_by=user.id,
            reason=body.correction_reason,
            previous_input=day.input_snapshot,
            new_input=snapshot,
        )
    )
    day.input_snapshot = snapshot
    db.flush()
    calculate_prediction(db, user, snapshot, plan_day=day, source="weekly")
    db.commit()
    return detail(db, plan)


@router.get("/{plan_id}/revisions")
def revisions(plan_id: UUID, db: Db, user: CurrentUser):
    plan = owned(db, WeeklyPrediction, plan_id, user)
    days = select(PredictionDay.id).where(
        PredictionDay.weekly_prediction_id == plan.id,
        PredictionDay.restaurant_id == user.restaurant_id,
    )
    return [
        serialize(row)
        for row in db.scalars(
            select(PlanRevision)
            .where(
                PlanRevision.restaurant_id == user.restaurant_id,
                PlanRevision.prediction_day_id.in_(days),
            )
            .order_by(PlanRevision.created_at.desc())
        ).all()
    ]
