"""Tes HTTP end-to-end pada API yang sedang berjalan.

Membuat restoran dan data DEMO tersendiri, bukan mengubah data restoran pengguna.
Password sesi demo acak tidak dicetak/disimpan, lalu sesi di-logout saat selesai.
"""

import argparse
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
import json
from pathlib import Path
import secrets
import time
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4
from zoneinfo import ZoneInfo


def run(base, mailpit_url):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    report = {"base_url": base, "status": "running", "steps": []}

    def call(method, path, body=None, expected=200, raw=None, content_type=None):
        data = json.dumps(body).encode() if body is not None else raw
        request = Request(base.rstrip("/") + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", content_type or "application/json")
        try:
            with opener.open(request, timeout=60) as response:
                status = response.status
                content = response.read()
        except HTTPError as exc:
            status = exc.code
            content = exc.read()
        report["steps"].append(
            {"method": method, "path": path, "expected": expected, "actual": status}
        )
        if status != expected:
            raise AssertionError(
                f'{method} {path}: HTTP {status}, diharapkan {expected}; {content[:600].decode(errors="replace")}'
            )
        if content.startswith((b"PK", b"%PDF-")):
            return content
        return json.loads(content) if content else None

    today = datetime.now(ZoneInfo("Asia/Jakarta")).date()
    try:
        call("GET", "/health/live")
        call("GET", "/health/ready")
        call("GET", "/api/v1/auth/me", expected=401)
        tag = uuid4().hex[:12]
        email = f"smoke_{tag}@example.test"
        owner = call(
            "POST",
            "/api/v1/auth/register",
            {
                "name": "Manager Uji Backend",
                "email": email,
                "password": secrets.token_urlsafe(24),
                "restaurant_name": "DEMO FoodSave Backend",
            },
            expected=201,
        )
        report.update(
            restaurant_id=owner["restaurant_id"], manager_id=owner["id"], demo_email=email
        )
        assert call("GET", "/api/v1/auth/me")["id"] == owner["id"]
        settings = call("GET", "/api/v1/settings")
        settings.pop("restaurant_id")
        settings.pop("updated_at")
        settings.update(ingredient_cost_per_kg=50000, safe_max_kg=0, warning_max_kg=0.01)
        call("PUT", "/api/v1/settings", settings)
        payload = {
            "operation_date": str(today),
            "meals_prepared": 400,
            "kitchen_staff": 12,
            "staff_experience": "intermediate",
            "special_event": False,
            "temperature_c": 28,
            "humidity_percent": 65,
            "previous_waste_kg": 20,
            "waste_category": "vegetables",
            "actual_waste_kg": 12.5,
            "manager_notes": "DEMO UJI BACKEND - bukan data operasional nyata.",
        }
        operation = call("POST", "/api/v1/daily-operations", payload, expected=201)
        report["daily_operation_id"] = operation["id"]
        prefix = "/api/v1/daily-operations/" + operation["id"]
        prediction = call("POST", prefix + "/predict", expected=201)
        assert prediction["model_version_id"] and prediction["predicted_waste_kg"] >= 0
        report["prediction_id"] = prediction["id"]
        report["predicted_waste_kg"] = prediction["predicted_waste_kg"]
        scenario = call(
            "POST",
            "/api/v1/portion-scenarios",
            {
                "daily_operation_id": operation["id"],
                "reduction_percent": 10,
                "application_date": str(today),
                "status": "saved",
                "notes": "DEMO simulasi.",
            },
            expected=201,
        )
        applied = call(
            "POST",
            f"/api/v1/portion-scenarios/{scenario['id']}/apply",
            {"expected_operation_version": 1},
        )
        assert (
            applied["operation"]["meals_prepared"] == 360 and applied["operation"]["version"] == 2
        )
        again = call(
            "POST",
            f"/api/v1/portion-scenarios/{scenario['id']}/apply",
            {"expected_operation_version": 1},
        )
        assert again["already_applied"] is True
        call("POST", "/api/v1/daily-operations", payload, expected=409)
        call(
            "PUT",
            prefix,
            {**payload, "expected_version": 1, "correction_reason": "DEMO uji versi lama."},
            expected=409,
        )
        assert len(call("GET", prefix + "/corrections")) == 1
        start = today + timedelta(days=1)
        plan = call(
            "POST",
            "/api/v1/weekly-predictions",
            {
                "title": "DEMO rencana tujuh hari",
                "starts_on": str(start),
                "days": [
                    {
                        **payload,
                        "operation_date": str(start + timedelta(days=i)),
                        "actual_waste_kg": None,
                    }
                    for i in range(7)
                ],
            },
            expected=201,
        )
        assert len(plan["days"]) == 7
        report["weekly_prediction_id"] = plan["id"]
        csv = (
            "operation_date,meals_prepared,kitchen_staff,staff_experience,temperature_c,humidity_percent\n"
            f"{today+timedelta(days=8)},200,10,Menengah,28,60\n{today+timedelta(days=9)},200,0,Pemula,28,60\n"
        )
        boundary = "FoodSave" + uuid4().hex
        multipart = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="demo-backend.csv"\r\n'
            f"Content-Type: text/csv\r\n\r\n{csv}\r\n--{boundary}--\r\n"
        ).encode()
        imported = call(
            "POST",
            "/api/v1/imports?apply=true",
            expected=201,
            raw=multipart,
            content_type=f"multipart/form-data; boundary={boundary}",
        )
        assert (
            imported["valid_rows"] == 1
            and imported["invalid_rows"] == 1
            and imported["applied_rows"] == 1
        )
        report["import_id"] = imported["id"]
        summary = call("GET", f"/api/v1/reports/summary?starts_on={today}&ends_on={today}")
        assert summary["operation_count"] == 1 and summary["total_actual_waste_kg"] == 12.5
        report["exports"] = []
        for format in ["pdf", "xlsx"]:
            export = call(
                "POST",
                "/api/v1/report-exports",
                {
                    "starts_on": str(today),
                    "ends_on": str(today),
                    "file_format": format,
                    "email_recipient": email,
                    "email_subject": f"DEMO FoodSave {format} {tag}",
                    "email_message": "Pengujian lokal Mailpit dan lampiran.",
                },
                expected=201,
            )
            assert export["generation_status"] == "ready"
            file = call("GET", f"/api/v1/report-exports/{export['id']}/file")
            assert file.startswith(b"%PDF-" if format == "pdf" else b"PK")
            report["exports"].append(export["id"])
        deadline = time.monotonic() + 40
        while True:
            histories = [
                call("GET", f"/api/v1/report-exports/{identity}/email")
                for identity in report["exports"]
            ]
            if all(h["email_status"] == "sent" for h in histories):
                break
            if time.monotonic() > deadline:
                raise AssertionError("Worker belum menyelesaikan email Mailpit dalam 40 detik.")
            time.sleep(1)
        with build_opener().open(
            mailpit_url.rstrip("/") + "/api/v1/messages", timeout=10
        ) as response:
            messages = json.load(response)["messages"]
        captured = [m for m in messages if tag in m.get("Subject", "")]
        assert len(captured) == 2 and all(m.get("Attachments", 0) == 1 for m in captured)
        report["mailpit_message_ids"] = [m["ID"] for m in captured]
        report["mailpit_capture"] = "passed: dua email lokal dengan lampiran PDF dan XLSX"
        task = call(
            "POST",
            "/api/v1/daily-tasks",
            {"task_date": str(today), "title": "DEMO timbang limbah"},
            expected=201,
        )
        assert call("PATCH", f"/api/v1/daily-tasks/{task['id']}", {"completed": True})[
            "completed_at"
        ]
        insight = call(
            "POST",
            "/api/v1/insights",
            {
                "title": "DEMO tinjau rencana",
                "suggested_action": "Periksa kebutuhan pelanggan sebelum mengurangi porsi.",
            },
            expected=201,
        )
        call("PATCH", f"/api/v1/insights/{insight['id']}", {"status": "reviewed"})
        notifications = call("GET", "/api/v1/notifications")
        assert notifications
        call("PATCH", f"/api/v1/notifications/{notifications[0]['id']}/read")
        overview = call("GET", f"/api/v1/overview?on={today}")
        assert (
            overview["operation"]["meals_prepared"] == 360
            and overview["prediction"]["operation_version"] == 2
        )
        call("POST", "/api/v1/auth/logout", expected=204)
        call("GET", "/api/v1/auth/me", expected=401)
        report["status"] = "passed"
        return report
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        path = Path(__file__).resolve().parents[1] / "results/backend/backend-test-report.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--mailpit-url", default="http://localhost:8025")
    args = parser.parse_args()
    result = run(args.url, args.mailpit_url)
    print(f"LULUS: {len(result['steps'])} langkah HTTP end-to-end.")
    print("Restoran DEMO:", result["restaurant_id"])
    print("Laporan pengecekan lokal: results/backend/backend-test-report.json")
