from datetime import date
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from api.auth import CurrentUser, Db, Manager, now
from api.models import (
    DailyOperation,
    DailyTask,
    Notification,
    OperationalInsight,
    PortionScenario,
    PredictionResult,
)
from api.schemas import InsightCreate, InsightStatus, TaskCreate, TaskStatus
from api.services import owned, restaurant_settings, serialize

router = APIRouter(tags=["Overview, tugas, insight, notifikasi"])


@router.get("/overview")
def overview(db: Db, user: CurrentUser, on: date):
    operation = db.scalar(
        select(DailyOperation).where(
            DailyOperation.restaurant_id == user.restaurant_id, DailyOperation.operation_date == on
        )
    )
    latest = None
    if operation:
        latest = db.scalar(
            select(PredictionResult)
            .where(
                PredictionResult.restaurant_id == user.restaurant_id,
                PredictionResult.daily_operation_id == operation.id,
                PredictionResult.operation_version == operation.version,
            )
            .order_by(PredictionResult.created_at.desc())
        )
    tasks = db.scalars(
        select(DailyTask)
        .where(DailyTask.restaurant_id == user.restaurant_id, DailyTask.task_date == on)
        .order_by(DailyTask.created_at)
    ).all()
    scenarios = db.scalars(
        select(PortionScenario).where(
            PortionScenario.restaurant_id == user.restaurant_id,
            PortionScenario.application_date == on,
            PortionScenario.status == "applied",
        )
    ).all()
    return {
        "operation": serialize(operation) if operation else None,
        "prediction": serialize(latest) if latest else None,
        "tasks": [serialize(t) for t in tasks],
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
        "reduction_target_percent": restaurant_settings(db, user).reduction_target_percent,
    }


@router.post("/daily-tasks", status_code=201)
def create_task(body: TaskCreate, db: Db, user: Manager):
    task = DailyTask(restaurant_id=user.restaurant_id, created_by=user.id, **body.model_dump())
    db.add(task)
    db.commit()
    return serialize(task)


@router.patch("/daily-tasks/{task_id}")
def complete_task(task_id: UUID, body: TaskStatus, db: Db, user: CurrentUser):
    task = owned(db, DailyTask, task_id, user)
    task.completed_at = now() if body.completed else None
    task.completed_by = user.id if body.completed else None
    db.commit()
    return serialize(task)


@router.get("/notifications")
def notifications(
    db: Db, user: CurrentUser, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
):
    rows = db.scalars(
        select(Notification)
        .where(Notification.restaurant_id == user.restaurant_id, Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return [serialize(row) for row in rows]


@router.patch("/notifications/{notification_id}/read")
def mark_read(notification_id: UUID, db: Db, user: CurrentUser):
    notification = owned(db, Notification, notification_id, user)
    if notification.user_id != user.id:
        raise HTTPException(404, "Notifikasi tidak ditemukan.")
    if notification.read_at is None:
        notification.read_at = now()
    db.commit()
    return serialize(notification)


@router.get("/insights")
def insights(
    db: Db,
    user: CurrentUser,
    status: str | None = Query(None, pattern="^(new|reviewed|applied)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(OperationalInsight).where(OperationalInsight.restaurant_id == user.restaurant_id)
    if status:
        query = query.where(OperationalInsight.status == status)
    return [
        serialize(row)
        for row in db.scalars(
            query.order_by(OperationalInsight.created_at.desc()).limit(limit).offset(offset)
        ).all()
    ]


@router.post("/insights", status_code=201)
def create_insight(body: InsightCreate, db: Db, user: Manager):
    if body.daily_operation_id:
        owned(db, DailyOperation, body.daily_operation_id, user)
    insight = OperationalInsight(
        restaurant_id=user.restaurant_id, created_by=user.id, **body.model_dump()
    )
    db.add(insight)
    db.commit()
    return serialize(insight)


@router.patch("/insights/{insight_id}")
def review_insight(insight_id: UUID, body: InsightStatus, db: Db, user: Manager):
    insight = owned(db, OperationalInsight, insight_id, user)
    insight.status = body.status
    insight.reviewed_at = now()
    insight.reviewed_by = user.id
    db.commit()
    return serialize(insight)
