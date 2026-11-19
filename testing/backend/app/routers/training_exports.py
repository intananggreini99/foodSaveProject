"""Riwayat dan pemicu manual ekspor data aktual ke HDFS (aliran balik untuk pelatihan ulang)."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import Db, Owner
from app.models import TrainingExport
from app.services.common import serialize
from app.services.training_export import run_export

router = APIRouter(prefix="/training-exports", tags=["Ekspor data aktual"])
HIDDEN = {"storage_path", "sha256", "created_by", "restaurant_count"}


@router.get("")
def list_exports(db: Db, user: Owner, limit: int = Query(30, ge=1, le=200)):
    # Catatan ekspor bersifat global (semua restoran); isi data tidak pernah dikirim ke klien.
    rows = db.scalars(
        select(TrainingExport).order_by(TrainingExport.created_at.desc()).limit(limit)
    ).all()
    return [serialize(row, exclude=HIDDEN) for row in rows]


@router.post("", status_code=201)
def trigger_export(db: Db, user: Owner):
    record = run_export(db, triggered_by="manual", user=user)
    db.commit()
    return serialize(record, exclude=HIDDEN)
