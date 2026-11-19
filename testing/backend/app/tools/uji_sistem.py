"""Uji end-to-end FoodSave lewat HTTP terhadap sistem yang sedang berjalan.

    docker compose exec api python -m app.tools.uji_sistem
    docker compose exec api python -m app.tools.uji_sistem --simpan   # data uji tidak dihapus

Membuat restoran uji sementara, menjalankan alur setiap halaman (input harian,
prediksi realtime, 7 hari, simulasi porsi, unggah CSV, dashboard, laporan + email,
notifikasi, insight, data model dari HDFS, keamanan), uji beban paralel, lalu
menghapus semua data restoran uji. Tidak memicu ekspor data aktual ke HDFS, jadi
data uji tidak pernah ikut melatih model.

Keluar dengan kode 1 bila ada pemeriksaan yang gagal.
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import httpx
from openpyxl import load_workbook
from sqlalchemy import text

PASSWORD = "UjiSistem-FoodSave-2026"
DELETE_ORDER = [
    "operational.notifications",
    "prediction.inference_logs",
    "operational.email_attempts",
    "operational.email_deliveries",
    "operational.report_exports",
    "prediction.portion_scenarios",
    "prediction.prediction_results",
    "prediction.plan_revisions",
    "prediction.prediction_days",
    "prediction.weekly_predictions",
    "operational.data_corrections",
    "operational.daily_operations",
    "operational.data_imports",
    "operational.user_sessions",
    "operational.restaurant_settings",
    "operational.users",
]


class Runner:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.client = httpx.Client(base_url=self.base, timeout=60)
        self.results: list[tuple[str, bool, float, str]] = []
        self.state: dict = {}

    def check(self, name: str, func):
        started = time.perf_counter()
        try:
            note = func() or ""
            ok = True
        except Exception as exc:  # noqa: BLE001 - semua kegagalan dilaporkan
            ok, note = False, f"{type(exc).__name__}: {exc}"
        elapsed = time.perf_counter() - started
        self.results.append((name, ok, elapsed, str(note)))
        mark = "LULUS" if ok else "GAGAL"
        print(f"[{mark}] {name} ({elapsed * 1000:.0f} ms){' - ' + str(note) if note else ''}",
              flush=True)
        return ok

    def call(self, method, path, expect, **kwargs):
        response = self.client.request(method, f"/api/v1{path}", **kwargs)
        expected = expect if isinstance(expect, tuple) else (expect,)
        if response.status_code not in expected:
            raise AssertionError(
                f"{method} {path} -> {response.status_code}, diharapkan {expected}: "
                f"{response.text[:200]}"
            )
        return response


def daily(day: date, **extra) -> dict:
    payload = {
        "operation_date": day.isoformat(), "meals_prepared": 420, "kitchen_staff": 12,
        "staff_experience": "intermediate", "special_event": False, "temperature_c": 29,
        "humidity_percent": 70, "waste_category": "sayur",
    }
    payload.update(extra)
    return payload


def plan_fields(payload: dict) -> dict:
    keys = ["operation_date", "meals_prepared", "kitchen_staff", "staff_experience",
            "special_event", "temperature_c", "humidity_percent"]
    return {k: payload[k] for k in keys}


def run_all(r: Runner, args) -> None:
    today = date.today()
    s = r.state
    stamp = uuid.uuid4().hex[:8]

    def health():
        live = r.client.get("/health/live")
        assert live.status_code == 200, live.text
        ready = r.client.get("/health/ready")
        assert ready.status_code == 200, f"belum siap: {ready.text[:200]}"
        s["model"] = ready.json()["model"]
        return f"model {s['model']}, penyimpanan {ready.json()['storage']}"

    def register():
        body = r.call("POST", "/auth/register", 201, json={
            "name": "Pemilik Uji", "email": f"uji-{stamp}@foodsave.test", "password": PASSWORD,
            "restaurant_name": f"Uji Sistem {stamp}"}).json()
        s["restaurant_id"], s["owner_id"] = body["restaurant_id"], body["id"]
        assert "password_hash" not in body
        me = r.call("GET", "/auth/me", 200).json()
        assert me["role"] == "owner"
        return f"restoran {s['restaurant_id']}"

    def settings():
        current = r.call("GET", "/settings", 200).json()
        update = {k: current[k] for k in ["safe_max_kg", "warning_max_kg", "max_portions",
                                          "reduction_target_percent"]}
        update["ingredient_cost_per_kg"] = 50000
        r.call("PUT", "/settings", 200, json=update)
        bad = dict(update, safe_max_kg=60, warning_max_kg=50)
        r.call("PUT", "/settings", 422, json=bad)
        return f"Aman <= {current['safe_max_kg']} kg, Waspada <= {current['warning_max_kg']} kg"

    def preview():
        normal = r.call("POST", "/predictions/preview", 200, json=plan_fields(daily(today))).json()
        assert normal["interval_lower_kg"] <= normal["predicted_waste_kg"] <= normal["interval_upper_kg"]
        odd = r.call("POST", "/predictions/preview", 200,
                     json=plan_fields(daily(today, meals_prepared=2000))).json()
        assert odd["outside_training_range"] is True
        return f"{normal['predicted_waste_kg']} kg ({normal['risk_level']})"

    def daily_input():
        op = r.call("POST", "/daily-operations", 201, json=daily(today)).json()
        r.call("POST", "/daily-operations", 409, json=daily(today))
        s["op"] = op
        pred = r.call("POST", f"/daily-operations/{op['id']}/predict", 201).json()
        s["pred"] = pred
        assert pred["model_version_id"]
        return f"prediksi {pred['predicted_waste_kg']} kg, risiko {pred['risk_level']}"

    def correction():
        op = s["op"]
        body = daily(today, actual_waste_kg=38.5)
        body.update(expected_version=1, correction_reason="Limbah aktual dicatat")
        updated = r.call("PUT", f"/daily-operations/{op['id']}", 200, json=body).json()
        assert updated["version"] == 2
        r.call("PUT", f"/daily-operations/{op['id']}", 409, json=body)
        history = r.call("GET", f"/daily-operations/{op['id']}/corrections", 200).json()
        assert len(history) == 1
        s["op"] = updated

    def dashboard():
        view = r.call("GET", "/dashboard", 200, params={"on": today.isoformat()}).json()
        assert view["prediction_is_stale"] is True
        r.call("POST", f"/daily-operations/{s['op']['id']}/predict", 201)
        view = r.call("GET", "/dashboard", 200, params={"on": today.isoformat()}).json()
        assert view["prediction_is_stale"] is False
        trend = r.call("GET", "/dashboard/trend", 200,
                       params={"end": today.isoformat(), "days": 7}).json()
        assert trend["paired_days"] == 1
        return f"MAE 7 hari {trend['mae_kg']} kg"

    def weekly():
        start = today + timedelta(days=1)
        days = [plan_fields(daily(start + timedelta(days=i), meals_prepared=300 + 25 * i))
                for i in range(7)]
        plan = r.call("POST", "/weekly-predictions", 201, json={
            "title": "Rencana uji", "starts_on": start.isoformat(), "days": days}).json()
        assert len(plan["days"]) == 7 and all(d["prediction"] for d in plan["days"])
        day = plan["days"][3]
        change = dict(day["input_snapshot"], meals_prepared=520,
                      expected_version=day["version"], correction_reason="Ada katering")
        r.call("PUT", f"/weekly-predictions/{plan['id']}/days/{day['id']}", 200, json=change)
        return "7 prediksi + 1 revisi"

    def scenarios():
        op = s["op"]
        options = r.call("POST", "/portion-scenarios/options", 200,
                         json={"daily_operation_id": op["id"]}).json()
        assert [o["reduction_percent"] for o in options["options"]] == [0, 5, 10, 15]
        scenario = r.call("POST", "/portion-scenarios", 201, json={
            "daily_operation_id": op["id"], "reduction_percent": 10,
            "application_date": today.isoformat(), "status": "saved"}).json()
        current = r.call("GET", f"/daily-operations/{op['id']}", 200).json()
        applied = r.call("POST", f"/portion-scenarios/{scenario['id']}/apply", 200,
                         json={"expected_operation_version": current["version"]}).json()
        assert applied["already_applied"] is False
        again = r.call("POST", f"/portion-scenarios/{scenario['id']}/apply", 200,
                       json={"expected_operation_version": current["version"] + 1}).json()
        assert again["already_applied"] is True
        best = min(options["options"], key=lambda o: o["predicted_waste_kg"])
        return f"pilihan terbaik {best['reduction_percent']}% ({best['predicted_waste_kg']} kg)"

    def csv_import():
        d1, d2 = today - timedelta(days=10), today - timedelta(days=9)
        content = (
            "date,meals_served,kitchen_staff,temperature_C,humidity_percent,special_event,"
            "staff_experience,waste_category,food_waste_kg\n"
            f"{d1},310,10,27,70,0,expert,daging,31.2\n"
            f"{d2},abc,10,27,70,0,expert,daging,10\n"
        ).encode()
        body = r.call("POST", "/imports", 201, params={"apply": "true"},
                      files={"file": ("uji.csv", io.BytesIO(content), "text/csv")}).json()
        assert body["valid_rows"] == 1 and body["invalid_rows"] == 1 and body["applied_rows"] == 1
        return "1 baris valid, 1 ditolak"

    def reports():
        summary = r.call("GET", "/reports/summary", 200, params={
            "starts_on": (today - timedelta(days=30)).isoformat(),
            "ends_on": today.isoformat()}).json()
        assert summary["operation_count"] >= 2
        for fmt, magic in (("pdf", b"%PDF-"), ("xlsx", b"PK")):
            job = r.call("POST", "/report-exports", 201, json={
                "starts_on": (today - timedelta(days=30)).isoformat(),
                "ends_on": today.isoformat(), "file_format": fmt}).json()
            file = r.call("GET", f"/report-exports/{job['id']}/file", 200).content
            assert file.startswith(magic), fmt
            if fmt == "xlsx":
                header = [c.value for c in load_workbook(io.BytesIO(file)).active[1]]
                assert "Prediksi kg" in header
        return f"{summary['operation_count']} hari, MAE prediksi {summary['prediction_mae_kg']}"

    def email():
        job = r.call("POST", "/report-exports", 201, json={
            "starts_on": (today - timedelta(days=7)).isoformat(), "ends_on": today.isoformat(),
            "file_format": "pdf", "email_recipient": f"penerima-{stamp}@example.test",
            "email_subject": "Laporan uji sistem"}).json()
        if job["email_status"] == "not_configured":
            return "email tidak dikonfigurasi (MAIL_BACKEND=disabled); dilewati"
        deadline = time.time() + args.tunggu_email
        status = job["email_status"]
        while time.time() < deadline and status == "pending":
            time.sleep(2)
            status = r.call("GET", f"/report-exports/{job['id']}", 200).json()["email_status"]
        assert status == "sent", f"status email {status}; periksa layanan report-worker"
        return "terkirim ke Mailpit"

    def notifications():
        current = r.call("GET", "/settings", 200).json()
        tight = {k: current[k] for k in ["ingredient_cost_per_kg", "max_portions",
                                         "reduction_target_percent"]}
        r.call("PUT", "/settings", 200, json={**tight, "safe_max_kg": 0.1, "warning_max_kg": 0.2})
        op = r.call("POST", "/daily-operations", 201,
                    json=daily(today - timedelta(days=1), special_event=True)).json()
        pred = r.call("POST", f"/daily-operations/{op['id']}/predict", 201).json()
        assert pred["risk_level"] == "high"
        notes = r.call("GET", "/notifications", 200).json()
        mine = [n for n in notes if n["prediction_result_id"] == pred["id"]]
        assert mine, "notifikasi risiko tinggi tidak dibuat"
        r.call("PATCH", f"/notifications/{mine[0]['id']}/read", 200)
        r.call("PUT", "/settings", 200, json={**tight, "safe_max_kg": current["safe_max_kg"],
                                              "warning_max_kg": current["warning_max_kg"]})

    def insights():
        view = r.call("GET", "/insights/operational", 200, params={
            "starts_on": (today - timedelta(days=30)).isoformat(),
            "ends_on": today.isoformat()}).json()
        assert sum(g["operation_count"] for g in view["staff_load"]) >= 2

    def model_static():
        active = r.call("GET", "/model/active", 200).json()
        assert active["version_key"] == s["model"] and active["loaded_in_memory"]
        scopes = {e["scope"] for e in r.call("GET", "/model/evaluations", 200).json()["items"]}
        assert scopes == {"cv_dev", "test", "baseline_test"}
        assert r.call("GET", "/model/tuning", 200).json()["trials"]
        assert r.call("GET", "/model/feature-importances", 200).json()["items"]
        curve = r.call("GET", "/model/sensitivity", 200).json()["points"]
        assert len(curve) >= 10
        rows = r.call("GET", "/model/evaluation-predictions", 200).json()["items"]
        assert rows and all(row["source"] == "seed" for row in rows)
        reports = r.call("GET", "/model/evaluation-reports", 200).json()["items"]
        pdf = next(x for x in reports if x["file_format"] == "pdf")
        file = r.call("GET", f"/model/evaluation-reports/{pdf['id']}/file", 200).content
        assert file.startswith(b"%PDF-")
        test = next(e for e in active["evaluations"] if e["scope"] == "test")
        return f"MAE test {test['mae']:.2f} kg, laporan evaluasi {len(file)} byte dari HDFS"

    def security():
        anonymous = httpx.Client(base_url=r.base, timeout=30)
        assert anonymous.get("/api/v1/daily-operations").status_code == 401
        evil = r.client.post("/api/v1/daily-operations", json=daily(today - timedelta(days=3)),
                             headers={"Origin": "https://situs-jahat.example"})
        assert evil.status_code == 403
        r.call("POST", "/auth/users", 201, json={
            "name": "Staf Uji", "email": f"staf-{stamp}@foodsave.test", "password": PASSWORD,
            "role": "staff"})
        staff = httpx.Client(base_url=r.base, timeout=30)
        staff.post("/api/v1/auth/login",
                   json={"email": f"staf-{stamp}@foodsave.test", "password": PASSWORD})
        assert staff.get(f"/api/v1/daily-operations/{s['op']['id']}").status_code == 200
        assert staff.post(f"/api/v1/daily-operations/{s['op']['id']}/predict").status_code == 403
        other = httpx.Client(base_url=r.base, timeout=30)
        other.post("/api/v1/auth/register", json={
            "name": "Lain", "email": f"lain-{stamp}@foodsave.test", "password": PASSWORD,
            "restaurant_name": f"Uji Sistem Lain {stamp}"})
        s["other_restaurant"] = other.get("/api/v1/auth/me").json()["restaurant_id"]
        assert other.get(f"/api/v1/daily-operations/{s['op']['id']}").status_code == 404

    def load_test():
        payload = plan_fields(daily(today))
        cookies = r.client.cookies

        def one(i):
            with httpx.Client(base_url=r.base, timeout=60, cookies=cookies) as c:
                started = time.perf_counter()
                body = dict(payload, meals_prepared=250 + i * 7)
                response = c.post("/api/v1/predictions/preview", json=body)
                return response.status_code, (time.perf_counter() - started) * 1000

        with ThreadPoolExecutor(max_workers=args.pekerja) as pool:
            results = list(pool.map(one, range(args.paralel)))
        codes = [c for c, _ in results]
        times = sorted(t for _, t in results)
        assert all(c == 200 for c in codes), f"status: {sorted(set(codes))}"
        p95 = times[max(0, int(len(times) * 0.95) - 1)]
        return (f"{len(codes)} permintaan, {args.pekerja} paralel, median "
                f"{statistics.median(times):.0f} ms, p95 {p95:.0f} ms")

    def logout():
        r.call("POST", "/auth/logout", 204)
        assert r.client.get("/api/v1/auth/me").status_code == 401

    steps = [
        ("Kesehatan sistem (database, HDFS, model aktif)", health),
        ("Daftar dan login pemilik", register),
        ("Pengaturan restoran dan validasi batas risiko", settings),
        ("Pratinjau prediksi saat mengetik", preview),
        ("Input data harian + prediksi realtime", daily_input),
        ("Koreksi data dengan versi (409 saat bentrok)", correction),
        ("Dashboard: tanda prediksi usang + tren MAE", dashboard),
        ("Prediksi 7 hari + ubah satu hari", weekly),
        ("Simulasi porsi: 4 pilihan, simpan, terapkan 2x", scenarios),
        ("Unggah CSV dengan validasi baris", csv_import),
        ("Laporan: ringkasan + ekspor PDF dan XLSX", reports),
        ("Email laporan lewat pekerja laporan", email),
        ("Notifikasi risiko tinggi", notifications),
        ("Insight operasional", insights),
        ("Data statis model + laporan evaluasi dari HDFS", model_static),
        ("Keamanan: login, origin, peran, isolasi restoran", security),
        ("Uji beban prediksi paralel", load_test),
        ("Logout", logout),
    ]
    for name, func in steps:
        ok = r.check(name, func)
        if not ok and name.startswith(("Kesehatan", "Daftar")):
            print("Pemeriksaan dasar gagal; langkah berikutnya dihentikan.")
            break


def cleanup(state: dict) -> None:
    from app.core import database
    from app.core.config import get_settings

    restaurants = [x for x in (state.get("restaurant_id"), state.get("other_restaurant")) if x]
    if not restaurants:
        return
    root = get_settings().app_storage_path
    with database.SessionLocal() as db:
        for restaurant_id in restaurants:
            keys = db.execute(text(
                "SELECT storage_key FROM operational.data_imports WHERE restaurant_id = :r"
                " UNION ALL SELECT storage_key FROM operational.report_exports"
                " WHERE restaurant_id = :r"), {"r": restaurant_id}).scalars().all()
            for table in DELETE_ORDER:
                db.execute(text(f"DELETE FROM {table} WHERE restaurant_id = :r"),
                           {"r": restaurant_id})
            db.execute(text("DELETE FROM operational.restaurants WHERE id = :r"),
                       {"r": restaurant_id})
            for key in keys:
                if key:
                    path = (root / key).resolve()
                    if path.is_relative_to(root.resolve()) and path.is_file():
                        path.unlink()
        db.commit()
    print(f"Data uji dihapus ({len(restaurants)} restoran).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Uji end-to-end FoodSave")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--simpan", action="store_true", help="Jangan hapus data uji")
    parser.add_argument("--paralel", type=int, default=40, help="Jumlah permintaan uji beban")
    parser.add_argument("--pekerja", type=int, default=8, help="Permintaan bersamaan")
    parser.add_argument("--tunggu-email", type=int, default=45, help="Detik menunggu email")
    args = parser.parse_args()
    runner = Runner(args.base_url)
    print(f"Uji sistem FoodSave terhadap {runner.base}\n")
    try:
        run_all(runner, args)
    finally:
        if not args.simpan:
            try:
                cleanup(runner.state)
            except Exception as exc:  # noqa: BLE001
                print(f"Pembersihan data uji gagal: {exc}")
    failed = [r for r in runner.results if not r[1]]
    total = sum(r[2] for r in runner.results)
    print(f"\n{len(runner.results) - len(failed)}/{len(runner.results)} pemeriksaan lulus"
          f" dalam {total:.1f} detik.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
