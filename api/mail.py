"""Pengiriman hanya ke Mailpit lokal sesuai lingkup pengujian proyek ini."""

from email.message import EmailMessage
from html import escape
import smtplib
from fastapi import HTTPException
from sqlalchemy import select
from api.auth import now
from api.config import get_settings
from api.models import EmailDelivery, Restaurant
from api.routers.imports import storage_file


def mail_enabled():
    return get_settings().mail_backend == "mailpit"


def queue_email(db, report, user_id):
    if not report.email_recipient:
        raise HTTPException(422, "Penerima email belum diisi.")
    if report.generation_status != "ready":
        raise HTTPException(409, "File laporan belum siap.")
    if not mail_enabled():
        raise HTTPException(503, "Mailpit belum diaktifkan.")
    existing = db.scalar(
        select(EmailDelivery).where(EmailDelivery.report_export_id == report.id).with_for_update()
    )
    if existing:
        if existing.status == "failed":
            existing.status = "pending"
            existing.max_attempts = existing.attempts + 3
            existing.next_attempt_at = now()
            existing.last_error = None
            report.email_status = "pending"
        elif existing.status == "pending":
            existing.next_attempt_at = now()
        return existing
    delivery = EmailDelivery(
        restaurant_id=report.restaurant_id,
        report_export_id=report.id,
        created_by=user_id,
        message_id=f"<foodsave-report-{report.id}@foodsave.test>",
        status="pending",
    )
    report.email_status = "pending"
    db.add(delivery)
    db.flush()
    return delivery


def build_message(db, report, delivery):
    settings = get_settings()
    restaurant = db.get(Restaurant, report.restaurant_id)
    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = report.email_recipient
    message["Subject"] = (
        report.email_subject or f"Laporan FoodSave {report.starts_on} sampai {report.ends_on}"
    )
    message["Message-ID"] = delivery.message_id
    message["X-FoodSave-Export-ID"] = str(report.id)
    text = report.email_message or "Berikut laporan operasional restoran yang diminta."
    message.set_content(
        f"{restaurant.name}\nPeriode: {report.starts_on} sampai {report.ends_on}\n\n{text}\n\nLampiran: {report.file_name}\nMode pengujian lokal Mailpit."
    )
    message.add_alternative(
        f"<html><body><h2>Laporan FoodSave</h2><p>{escape(restaurant.name)}</p>"
        f'<p>Periode: {report.starts_on} sampai {report.ends_on}</p><p>{escape(text).replace(chr(10),"<br>")}</p>'
        "<p>Laporan ada pada lampiran. Email ini ditangkap Mailpit lokal.</p></body></html>",
        subtype="html",
    )
    path = storage_file(report.storage_key)
    if not path.is_file():
        raise OSError("File laporan tidak tersedia.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise ValueError("Lampiran maksimal 10 MB.")
    subtype = (
        "pdf"
        if report.file_format == "pdf"
        else "vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    message.add_attachment(
        path.read_bytes(), maintype="application", subtype=subtype, filename=report.file_name
    )
    return message


def send_message(message):
    settings = get_settings()
    # Mencegah konfigurasi mode uji ini tanpa sengaja diarahkan ke SMTP luar.
    if not mail_enabled() or settings.smtp_host.strip().lower() not in {
        "mailpit",
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("Pengiriman hanya diizinkan ke Mailpit lokal.")
    with smtplib.SMTP(
        settings.smtp_host.strip(), settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as server:
        refused = server.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
