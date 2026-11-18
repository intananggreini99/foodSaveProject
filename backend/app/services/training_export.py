"""Aliran balik data: limbah aktual dari daily_operations diekspor ke HDFS /foodsave/raw/actuals.

Setiap ekspor mengambil input harian yang sudah punya limbah aktual dan berubah
sejak ekspor berhasil terakhir. Pipeline MLflow membaca semua file di folder
itu; bila satu operasi terekspor lebih dari sekali, hanya ekspor terbaru dipakai.
"""

from __future__ import annotations

import csv
import io
import logging

from sqlalchemy import select

from app.core.security import now
from app.models import DailyOperation, TrainingExport
from app.services.common import model_storage
from foodsave_core.features import EXPORT_EXTRA_COLUMNS, RAW_COLUMNS, operation_to_raw_row
from foodsave_core.storage import RAW_ACTUALS_DIR, sha256

log = logging.getLogger("foodsave.training_export")


def run_export(db, triggered_by: str = "schedule", user=None) -> TrainingExport:
    until = now()
    last = db.scalar(
        select(TrainingExport)
        .where(TrainingExport.status == "completed")
        .order_by(TrainingExport.changed_until.desc())
        .limit(1)
    )
    since = last.changed_until if last else None
    query = select(DailyOperation).where(
        DailyOperation.actual_waste_kg.is_not(None), DailyOperation.updated_at <= until
    )
    if since is not None:
        query = query.where(DailyOperation.updated_at > since)
    rows = db.scalars(query.order_by(DailyOperation.operation_date, DailyOperation.id)).all()
    record = TrainingExport(
        triggered_by=triggered_by,
        created_by=user.id if user else None,
        changed_since=since,
        changed_until=until,
        row_count=len(rows),
        restaurant_count=len({r.restaurant_id for r in rows}),
        first_operation_date=rows[0].operation_date if rows else None,
        last_operation_date=rows[-1].operation_date if rows else None,
        status="empty",
    )
    if rows:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=RAW_COLUMNS + EXPORT_EXTRA_COLUMNS)
        writer.writeheader()
        for row in rows:
            raw = operation_to_raw_row(
                {c.key: getattr(row, c.key) for c in DailyOperation.__table__.columns}
            )
            raw.update(
                {
                    "source": "actuals",
                    "operation_id": str(row.id),
                    "restaurant_ref": str(row.restaurant_id),
                    "exported_at": until.isoformat(),
                }
            )
            writer.writerow(raw)
        content = buffer.getvalue().encode()
        path = f"{RAW_ACTUALS_DIR}/actuals_{until:%Y%m%dT%H%M%S}.csv"
        storage = model_storage()
        try:
            storage.makedirs(RAW_ACTUALS_DIR)
            storage.write_bytes(path, content, overwrite=False)
        except Exception as exc:  # noqa: BLE001 - dicatat sebagai ekspor gagal
            log.exception("Ekspor data aktual gagal")
            record.status = "failed"
            record.error_message = f"Penyimpanan HDFS gagal: {type(exc).__name__}"[:500]
        else:
            record.status = "completed"
            record.storage_path = path
            record.sha256 = sha256(content)
    db.add(record)
    db.flush()
    log.info("Ekspor data aktual: %s baris, status %s", record.row_count, record.status)
    return record
