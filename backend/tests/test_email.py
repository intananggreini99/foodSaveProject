from datetime import datetime, timezone
from email.message import EmailMessage
from uuid import UUID
import pytest
from sqlalchemy import select
from app.core.config import get_settings
from app.workers.report_worker import process_one
from app.models import EmailDelivery


@pytest.fixture
def enabled_mail(monkeypatch):
    monkeypatch.setattr(get_settings(), "mail_backend", "mailpit")


def create_export(client):
    response = client.post(
        "/api/v1/report-exports",
        json={
            "starts_on": "2026-11-01",
            "ends_on": "2026-11-30",
            "file_format": "pdf",
            "email_recipient": "manager@example.test",
            "email_subject": "Laporan uji Mailpit",
            "email_message": "Tinjau laporan terlampir.",
        },
    )
    assert response.status_code == 201, response.text
    assert (
        response.json()["generation_status"] == "ready"
        and response.json()["email_status"] == "pending"
    )
    return response.json()


def test_email_outbox_message_attachment_and_idempotency(
    client, owner, enabled_mail, factory, monkeypatch
):
    import app.workers.report_worker as worker

    sent = []
    monkeypatch.setattr(worker, "send_message", sent.append)
    export = create_export(client)
    with factory() as db:
        assert process_one(db) is True
    history = client.get(f"/api/v1/report-exports/{export['id']}/email").json()
    assert history["email_status"] == "sent" and history["delivery"]["transport"] == "mailpit"
    assert history["delivery"]["attempts"] == 1 and history["attempts"][0]["success"] is True
    assert len(sent) == 1 and sent[0]["To"] == "manager@example.test"
    attachments = list(sent[0].iter_attachments())
    assert len(attachments) == 1
    assert attachments[0].get_payload(decode=True).startswith(b"%PDF-")
    assert sent[0]["Message-ID"] == history["delivery"]["message_id"]
    assert (
        client.post(f"/api/v1/report-exports/{export['id']}/email/retry").json()["status"] == "sent"
    )
    with factory() as db:
        assert process_one(db) is False
    assert len(sent) == 1


def test_smtp_failure_retries_without_losing_history(
    client, owner, enabled_mail, factory, monkeypatch
):
    import app.workers.report_worker as worker

    def fail(message):
        raise OSError("Mailpit uji offline.")

    monkeypatch.setattr(worker, "send_message", fail)
    export = create_export(client)
    with factory() as db:
        assert process_one(db)
    history = client.get(f"/api/v1/report-exports/{export['id']}/email").json()
    assert history["delivery"]["status"] == "pending" and history["delivery"]["attempts"] == 1
    assert history["attempts"][0]["success"] is False and history["delivery"]["last_error"]
    assert client.post(f"/api/v1/report-exports/{export['id']}/email/retry").status_code == 200
    monkeypatch.setattr(worker, "send_message", lambda message: None)
    with factory() as db:
        assert process_one(db)
    history = client.get(f"/api/v1/report-exports/{export['id']}/email").json()
    assert history["email_status"] == "sent" and len(history["attempts"]) == 2
    assert history["attempts"][-1]["success"] is True


def test_exhausted_retries_can_be_manually_resumed(
    client, owner, enabled_mail, factory, monkeypatch
):
    import app.workers.report_worker as worker

    def fail(message):
        raise OSError("Mailpit uji offline.")

    monkeypatch.setattr(worker, "send_message", fail)
    export = create_export(client)
    for i in range(3):
        with factory() as db:
            delivery = db.scalar(
                select(EmailDelivery).where(EmailDelivery.report_export_id == UUID(export["id"]))
            )
            delivery.next_attempt_at = datetime.now(timezone.utc)
            db.commit()
            assert process_one(db)
    history = client.get(f"/api/v1/report-exports/{export['id']}/email").json()
    assert history["email_status"] == "failed" and history["delivery"]["attempts"] == 3
    retry = client.post(f"/api/v1/report-exports/{export['id']}/email/retry").json()
    assert retry["status"] == "pending" and retry["max_attempts"] == 6 and retry["attempts"] == 3
    monkeypatch.setattr(worker, "send_message", lambda message: None)
    with factory() as db:
        assert process_one(db)
    assert len(client.get(f"/api/v1/report-exports/{export['id']}/email").json()["attempts"]) == 4


def test_mailpit_mode_never_connects_to_external_smtp(monkeypatch):
    import app.services.mail as mail

    monkeypatch.setattr(get_settings(), "mail_backend", "mailpit")
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.gmail.com")

    def forbidden(*args, **kwargs):
        raise AssertionError("Tidak boleh membuka koneksi SMTP luar.")

    monkeypatch.setattr(mail.smtplib, "SMTP", forbidden)
    with pytest.raises(ValueError):
        mail.send_message(EmailMessage())


def test_email_subject_rejects_header_injection(client, owner):
    response = client.post(
        "/api/v1/report-exports",
        json={
            "starts_on": "2026-11-01",
            "ends_on": "2026-11-30",
            "file_format": "pdf",
            "email_recipient": "manager@example.test",
            "email_subject": "Subjek\r\nBcc: other@example.test",
        },
    )
    assert response.status_code == 422


def test_email_history_and_retry_are_isolated_per_restaurant(client, owner, enabled_mail):
    from fastapi.testclient import TestClient
    from app.main import app
    from tests.conftest import register

    export = create_export(client)
    with TestClient(app) as other:
        register(other, "email-other@example.test", "Restoran Lain")
        assert other.get(f"/api/v1/report-exports/{export['id']}/email").status_code == 404
        assert other.post(f"/api/v1/report-exports/{export['id']}/email/retry").status_code == 404
