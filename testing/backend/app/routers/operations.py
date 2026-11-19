"""Halaman Input Data Harian: simpan, ubah (dengan alasan koreksi), dan riwayat."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.deps import CurrentUser, Db, Manager
from app.models import DailyOperation, DataCorrection
from app.schemas import DailyInput, DailyUpdate
from app.services.common import daily_snapshot, ensure_capacity, owned, restaurant_settings, serialize

router = APIRouter(tags=["Input data harian"])


@router.post("/daily-operations", status_code=201)
def create_operation(body: DailyInput, db: Db, user: Manager):
    ensure_capacity(body, restaurant_settings(db, user))
    if db.scalar(
        select(DailyOperation.id).where(
            DailyOperation.restaurant_id == user.restaurant_id,
            DailyOperation.operation_date == body.operation_date,
        )
    ):
        raise HTTPException(409, "Tanggal ini sudah memiliki data. Gunakan endpoint ubah data.")
    row = DailyOperation(
        restaurant_id=user.restaurant_id,
        created_by=user.id,
        updated_by=user.id,
        **body.model_dump(),
    )
    db.add(row)
    db.commit()
    return serialize(row)


@router.get("/daily-operations")
def list_operations(
    db: Db,
    user: CurrentUser,
    starts_on: date | None = None,
    ends_on: date | None = None,
    waste_category: str | None = None,
    search: str | None = Query(None, max_length=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(DailyOperation).where(DailyOperation.restaurant_id == user.restaurant_id)
    if starts_on:
        query = query.where(DailyOperation.operation_date >= starts_on)
    if ends_on:
        query = query.where(DailyOperation.operation_date <= ends_on)
    if waste_category:
        query = query.where(DailyOperation.waste_category == waste_category)
    if search:
        query = query.where(DailyOperation.manager_notes.ilike("%" + search + "%"))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(DailyOperation.operation_date.desc()).offset(offset).limit(limit)
    ).all()
    return {
        "items": [serialize(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/daily-operations/{operation_id}")
def get_operation(operation_id: UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, DailyOperation, operation_id, user))


@router.put("/daily-operations/{operation_id}")
def update_operation(operation_id: UUID, body: DailyUpdate, db: Db, user: Manager):
    row = owned(db, DailyOperation, operation_id, user, lock=True)
    if row.version != body.expected_version:
        raise HTTPException(409, "Data sudah diubah pengguna lain. Muat ulang terlebih dahulu.")
    ensure_capacity(body, restaurant_settings(db, user))
    old = daily_snapshot(row)
    values = body.model_dump(exclude={"expected_version", "correction_reason"})
    db.add(
        DataCorrection(
            restaurant_id=user.restaurant_id,
            daily_operation_id=row.id,
            changed_by=user.id,
            reason=body.correction_reason,
            previous_version=row.version,
            previous_values=old,
            new_values=DailyInput.model_validate(values).model_dump(mode="json"),
        )
    )
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = user.id
    db.commit()
    return serialize(row)


@router.get("/daily-operations/{operation_id}/corrections")
def corrections(operation_id: UUID, db: Db, user: CurrentUser):
    owned(db, DailyOperation, operation_id, user)
    return [
        serialize(row)
        for row in db.scalars(
            select(DataCorrection)
            .where(
                DataCorrection.restaurant_id == user.restaurant_id,
                DataCorrection.daily_operation_id == operation_id,
            )
            .order_by(DataCorrection.created_at.desc())
        ).all()
    ]
