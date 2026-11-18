"""Halaman Notifikasi: dibuat otomatis saat prediksi realtime berstatus Tinggi."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, Db
from app.core.security import now
from app.models import Notification
from app.services.common import owned, serialize

router = APIRouter(prefix="/notifications", tags=["Notifikasi"])


@router.get("")
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


@router.patch("/{notification_id}/read")
def mark_read(notification_id: UUID, db: Db, user: CurrentUser):
    notification = owned(db, Notification, notification_id, user)
    if notification.user_id != user.id:
        raise HTTPException(404, "Notifikasi tidak ditemukan.")
    if notification.read_at is None:
        notification.read_at = now()
    db.commit()
    return serialize(notification)
