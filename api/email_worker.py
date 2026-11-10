"""Worker outbox PostgreSQL dengan row lock, retry, dan catatan setiap usaha."""

import argparse
from datetime import timedelta
import logging
import smtplib
import time
from sqlalchemy import select
from api.auth import now
from api.database import SessionLocal
from api.mail import build_message, mail_enabled, send_message
from api.models import EmailAttempt, EmailDelivery, ReportExport

logger = logging.getLogger(__name__)


def process_one(db):
    delivery = db.scalar(
        select(EmailDelivery)
        .where(
            EmailDelivery.status == "pending",
            EmailDelivery.next_attempt_at <= now(),
            EmailDelivery.attempts < EmailDelivery.max_attempts,
        )
        .order_by(EmailDelivery.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if delivery is None:
        return False
    report = db.get(ReportExport, delivery.report_export_id)
    delivery.attempts += 1
    try:
        if report.restaurant_id != delivery.restaurant_id:
            raise ValueError("Restoran pada antrean tidak sesuai.")
        message = build_message(db, report, delivery)
        send_message(message)
        delivery.status = "sent"
        delivery.sent_at = now()
        delivery.last_error = None
        report.email_status = "sent"
        db.add(
            EmailAttempt(
                restaurant_id=delivery.restaurant_id,
                email_delivery_id=delivery.id,
                attempt_number=delivery.attempts,
                success=True,
            )
        )
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        error = "Mailpit atau lampiran tidak tersedia. Periksa layanan dan file laporan."
        logger.warning("Email %s gagal (%s)", delivery.id, type(exc).__name__)
        delivery.last_error = error
        delivery.status = "failed" if delivery.attempts >= delivery.max_attempts else "pending"
        delivery.next_attempt_at = now() + timedelta(
            seconds=60 * 2 ** min(delivery.attempts - 1, 5)
        )
        report.email_status = delivery.status
        db.add(
            EmailAttempt(
                restaurant_id=delivery.restaurant_id,
                email_delivery_id=delivery.id,
                attempt_number=delivery.attempts,
                success=False,
                error_message=error,
            )
        )
    db.commit()
    return True


def main(once=False):
    logging.basicConfig(level=logging.INFO)
    if not mail_enabled():
        raise SystemExit("MAIL_BACKEND harus mailpit untuk menjalankan worker.")
    while True:
        try:
            with SessionLocal() as db:
                processed = process_one(db)
        except Exception:
            logger.exception("Worker email gagal; transaksi di-rollback.")
            processed = False
        if once:
            return
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    main(parser.parse_args().once)
