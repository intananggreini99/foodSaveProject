"""Angka laporan dihitung dari input aktual; ekspor/email dicatat sebagai job."""

from datetime import date
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from api.auth import CurrentUser, Db, Manager, now
from api.models import DailyOperation, EmailAttempt, EmailDelivery, ReportExport
from api.schemas import ReportRequest
from api.services import owned, restaurant_settings, serialize

router = APIRouter(tags=["Ringkasan dan permintaan laporan"])


@router.get("/reports/summary")
def report_summary(
    db: Db, user: CurrentUser, starts_on: date, ends_on: date, waste_category: str | None = None
):
    if ends_on < starts_on:
        raise HTTPException(422, "Tanggal akhir harus setelah tanggal mulai.")
    query = select(DailyOperation).where(
        DailyOperation.restaurant_id == user.restaurant_id,
        DailyOperation.operation_date >= starts_on,
        DailyOperation.operation_date <= ends_on,
    )
    if waste_category:
        query = query.where(DailyOperation.waste_category == waste_category)
    sub = query.subquery()
    total, count_actual, total_actual, mean_actual, portions = db.execute(
        select(
            func.count(),
            func.count(sub.c.actual_waste_kg),
            func.sum(sub.c.actual_waste_kg),
            func.avg(sub.c.actual_waste_kg),
            func.sum(sub.c.meals_prepared),
        )
    ).one()
    cost = restaurant_settings(db, user).ingredient_cost_per_kg
    grouped = db.execute(
        select(sub.c.waste_category, func.count(), func.sum(sub.c.actual_waste_kg)).group_by(
            sub.c.waste_category
        )
    ).all()
    return {
        "starts_on": starts_on,
        "ends_on": ends_on,
        "operation_count": total,
        "actual_recorded_count": count_actual,
        "actual_missing_count": total - count_actual,
        "total_actual_waste_kg": total_actual,
        "average_actual_waste_kg": mean_actual,
        "total_portions": portions or 0,
        "estimated_actual_waste_cost": total_actual * cost if total_actual is not None else None,
        "cost_basis": "Harga bahan per kg pada pengaturan saat laporan diminta; bukan biaya historis akuntansi.",
        "by_category": [
            {"category": category, "operation_count": n, "actual_waste_kg": kg}
            for category, n, kg in grouped
        ],
    }


@router.post("/report-exports", status_code=201)
def request_export(body: ReportRequest, db: Db, user: Manager):
    from api.exports import write_export
    from api.mail import mail_enabled, queue_email
    from api.routers.imports import storage_file

    row = ReportExport(
        restaurant_id=user.restaurant_id,
        created_by=user.id,
        **body.model_dump(),
        generation_status="requested",
        email_status="not_configured" if body.email_recipient else "not_requested",
    )
    db.add(row)
    db.flush()
    try:
        row.storage_key, row.file_name = write_export(db, row)
        row.generation_status = "ready"
        if row.email_recipient and mail_enabled():
            queue_email(db, row, user.id)
    except SQLAlchemyError:
        file = storage_file(f"reports/{row.id}.{row.file_format}")
        if file.exists():
            file.unlink()
        raise
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Pembuatan laporan gagal")
        # Tidak mengklaim file/email selesai apabila pembuatan file gagal.
        file = storage_file(f"reports/{row.id}.{row.file_format}")
        if file.exists():
            file.unlink()
        row.generation_status = "failed"
        if row.email_recipient:
            row.email_status = "failed"
    try:
        db.commit()
    except SQLAlchemyError:
        file = storage_file(f"reports/{row.id}.{row.file_format}")
        if file.exists():
            file.unlink()
        raise
    return serialize(row)


@router.get("/report-exports/{export_id}/email")
def email_history(export_id: UUID, db: Db, user: CurrentUser):
    export = owned(db, ReportExport, export_id, user)
    delivery = db.scalar(
        select(EmailDelivery).where(
            EmailDelivery.restaurant_id == user.restaurant_id,
            EmailDelivery.report_export_id == export.id,
        )
    )
    attempts = []
    if delivery:
        attempts = [
            serialize(row)
            for row in db.scalars(
                select(EmailAttempt)
                .where(
                    EmailAttempt.restaurant_id == user.restaurant_id,
                    EmailAttempt.email_delivery_id == delivery.id,
                )
                .order_by(EmailAttempt.attempt_number)
            ).all()
        ]
    return {
        "email_status": export.email_status,
        "delivery": serialize(delivery) if delivery else None,
        "attempts": attempts,
    }


@router.post("/report-exports/{export_id}/email/retry")
def retry_email(export_id: UUID, db: Db, user: Manager):
    from api.mail import queue_email

    # Worker mengunci delivery terlebih dahulu; jangan mengunci parent dulu.
    export = owned(db, ReportExport, export_id, user)
    delivery = queue_email(db, export, user.id)
    db.commit()
    return serialize(delivery)


@router.get("/report-exports")
def list_exports(
    db: Db, user: CurrentUser, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)
):
    return [
        serialize(row)
        for row in db.scalars(
            select(ReportExport)
            .where(ReportExport.restaurant_id == user.restaurant_id)
            .order_by(ReportExport.created_at.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    ]


@router.get("/report-exports/{export_id}")
def read_export(export_id: UUID, db: Db, user: CurrentUser):
    return serialize(owned(db, ReportExport, export_id, user))


@router.get("/report-exports/{export_id}/file")
def download_export(export_id: UUID, db: Db, user: CurrentUser):
    from api.routers.imports import storage_file

    row = owned(db, ReportExport, export_id, user)
    if row.generation_status != "ready" or not row.storage_key:
        raise HTTPException(409, "File belum dibuat oleh layanan ekspor.")
    path = storage_file(row.storage_key)
    if not path.is_file():
        raise HTTPException(404, "File laporan tidak ditemukan.")
    row.downloaded_at = now()
    db.commit()
    return FileResponse(path, filename=row.file_name)
