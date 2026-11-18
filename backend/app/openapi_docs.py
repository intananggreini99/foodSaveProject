"""Penataan Swagger UI (/docs) untuk mencoba fitur FoodSave tanpa frontend.

Endpoint dikelompokkan per halaman fitur dan diberi judul bahasa Indonesia, berurutan
sesuai alur pengujian. Modul ini hanya mengubah dokumen OpenAPI; perilaku endpoint tidak
berubah.
"""

AKUN = "1. Akun dan login"
PENGATURAN = "2. Pengaturan restoran"
INPUT = "3. Input Data Harian"
UNGGAH = "4. Unggah CSV/Excel"
DASHBOARD = "5. Dashboard"
MINGGUAN = "6. Prediksi 7 Hari"
SIMULASI = "7. Simulasi Porsi"
INSIGHT = "8. Insight & Penyebab"
LAPORAN = "9. Laporan"
NOTIFIKASI = "10. Notifikasi"
MODEL = "11. Model dan pelatihan ulang"
STATUS = "Status sistem"

TAGS = [
    {
        "name": AKUN,
        "description": "Mulai di sini. Jalankan **Daftar akun** (atau **Masuk**). Browser menyimpan "
        "cookie sesi, jadi endpoint lain langsung bisa dicoba. Tidak perlu tombol Authorize.",
    },
    {
        "name": PENGATURAN,
        "description": "Harga bahan per kg dipakai untuk estimasi biaya; batas Aman dan Waspada "
        "menentukan tingkat risiko prediksi. Mengubah data butuh peran pemilik atau manager.",
    },
    {
        "name": INPUT,
        "description": "Alur: (1) **Pratinjau prediksi**, (2) **Simpan input harian** lalu salin "
        "`id` dari respons, (3) **Jalankan dan simpan prediksi** dengan `id` itu. Koreksi memakai "
        "`expected_version` dari respons terakhir. Tanggal yang sudah dipakai ditolak (409).",
    },
    {
        "name": UNGGAH,
        "description": "Pilih file CSV/XLSX, misalnya `docs/contoh/daily_operations.csv`. Jalankan "
        "dulu dengan `apply=false` untuk memeriksa, lalu `apply=true` untuk menyimpan baris valid. "
        "Baris hasil unggahan belum diprediksi.",
    },
    {
        "name": DASHBOARD,
        "description": "Isi `on`/`end` dengan tanggal (YYYY-MM-DD) yang sudah punya input harian.",
    },
    {
        "name": MINGGUAN,
        "description": "Body contoh sudah berisi 7 hari berurutan. Untuk mengubah satu hari, ambil "
        "`plan_id`, `id` hari, dan `version` hari dari respons rencana; `operation_date` harus sama "
        "dengan tanggal hari itu.",
    },
    {
        "name": SIMULASI,
        "description": "Ganti `daily_operation_id` dengan `id` input harian dari kelompok 3, dan "
        "`application_date` dengan tanggal input itu. Untuk menerapkan skenario, isi "
        "`expected_operation_version` dengan `version` input saat ini.",
    },
    {
        "name": INSIGHT,
        "description": "Analisis model dihitung sekali oleh pipeline MLflow (statis). Insight "
        "operasional dihitung dari input restoran Anda.",
    },
    {
        "name": LAPORAN,
        "description": "Isi tanggal mulai dan selesai. File diunduh lewat **Unduh file laporan**. "
        "Email ditangkap Mailpit lokal (http://localhost:8026).",
    },
    {"name": NOTIFIKASI, "description": "Notifikasi muncul saat prediksi masuk kategori Tinggi."},
    {
        "name": MODEL,
        "description": "Model baru dibuat dengan `docker compose run --rm trainer` dan langsung "
        "dipakai API.",
    },
    {"name": STATUS, "description": "Tidak butuh login."},
]

P = "/api/v1"
ROUTES = {
    ("GET", "/health/live"): (STATUS, "Cek API hidup"),
    ("GET", "/health/ready"): (STATUS, "Cek kesiapan: database, HDFS, model aktif"),
    # 1. Akun
    ("POST", f"{P}/auth/register"): (AKUN, "Daftar akun pemilik dan restoran baru (langsung login)"),
    ("POST", f"{P}/auth/login"): (AKUN, "Masuk"),
    ("POST", f"{P}/auth/logout"): (AKUN, "Keluar"),
    ("GET", f"{P}/auth/me"): (AKUN, "Lihat akun yang sedang login"),
    ("PUT", f"{P}/auth/me"): (AKUN, "Ubah nama dan preferensi notifikasi"),
    ("GET", f"{P}/auth/sessions"): (AKUN, "Daftar sesi login"),
    ("DELETE", f"{P}/auth/sessions/{{session_id}}"): (AKUN, "Akhiri satu sesi login"),
    ("POST", f"{P}/auth/users"): (AKUN, "Tambah manager atau staf (khusus pemilik)"),
    # 2. Pengaturan
    ("GET", f"{P}/restaurant"): (PENGATURAN, "Lihat restoran"),
    ("PUT", f"{P}/restaurant"): (PENGATURAN, "Ubah nama restoran"),
    ("GET", f"{P}/users"): (PENGATURAN, "Daftar anggota tim"),
    ("GET", f"{P}/settings"): (PENGATURAN, "Lihat harga bahan dan batas risiko"),
    ("PUT", f"{P}/settings"): (PENGATURAN, "Ubah harga bahan, batas risiko, dan kapasitas"),
    # 3. Input Data Harian
    ("POST", f"{P}/predictions/preview"): (INPUT, "Pratinjau prediksi tanpa menyimpan"),
    ("POST", f"{P}/daily-operations"): (INPUT, "Simpan input harian"),
    ("POST", f"{P}/daily-operations/{{operation_id}}/predict"): (
        INPUT,
        "Jalankan dan simpan prediksi untuk input harian",
    ),
    ("GET", f"{P}/daily-operations"): (INPUT, "Riwayat input harian"),
    ("GET", f"{P}/daily-operations/{{operation_id}}"): (INPUT, "Detail satu input harian"),
    ("PUT", f"{P}/daily-operations/{{operation_id}}"): (INPUT, "Koreksi input harian"),
    ("GET", f"{P}/daily-operations/{{operation_id}}/corrections"): (INPUT, "Riwayat koreksi input"),
    ("GET", f"{P}/predictions"): (INPUT, "Riwayat hasil prediksi"),
    ("GET", f"{P}/predictions/{{prediction_id}}"): (INPUT, "Detail satu hasil prediksi"),
    # 4. Unggah
    ("POST", f"{P}/imports"): (UNGGAH, "Unggah CSV/Excel (apply=false periksa, apply=true simpan)"),
    ("GET", f"{P}/imports"): (UNGGAH, "Riwayat unggahan"),
    ("GET", f"{P}/imports/{{import_id}}"): (UNGGAH, "Detail hasil pemeriksaan unggahan"),
    ("GET", f"{P}/imports/{{import_id}}/file"): (UNGGAH, "Unduh file yang diunggah"),
    # 5. Dashboard
    ("GET", f"{P}/dashboard"): (DASHBOARD, "Ringkasan satu tanggal: input, prediksi, risiko"),
    ("GET", f"{P}/dashboard/trend"): (DASHBOARD, "Aktual vs prediksi per tanggal"),
    # 6. Prediksi 7 Hari
    ("POST", f"{P}/weekly-predictions"): (MINGGUAN, "Buat rencana 7 hari (7 prediksi sekaligus)"),
    ("GET", f"{P}/weekly-predictions"): (MINGGUAN, "Daftar rencana"),
    ("GET", f"{P}/weekly-predictions/{{plan_id}}"): (MINGGUAN, "Detail rencana dan prediksi per hari"),
    ("PUT", f"{P}/weekly-predictions/{{plan_id}}/days/{{day_id}}"): (
        MINGGUAN,
        "Ubah satu hari lalu prediksi ulang",
    ),
    ("GET", f"{P}/weekly-predictions/{{plan_id}}/revisions"): (MINGGUAN, "Riwayat revisi rencana"),
    # 7. Simulasi Porsi
    ("POST", f"{P}/portion-scenarios/options"): (
        SIMULASI,
        "Bandingkan pengurangan 0/5/10/15% (tanpa menyimpan)",
    ),
    ("POST", f"{P}/portion-scenarios"): (SIMULASI, "Simpan skenario"),
    ("GET", f"{P}/portion-scenarios"): (SIMULASI, "Daftar skenario"),
    ("GET", f"{P}/portion-scenarios/{{scenario_id}}"): (SIMULASI, "Detail skenario"),
    ("POST", f"{P}/portion-scenarios/{{scenario_id}}/apply"): (
        SIMULASI,
        "Terapkan skenario ke input harian",
    ),
    # 8. Insight
    ("GET", f"{P}/insights/operational"): (INSIGHT, "Beban staf dan limbah per kategori"),
    ("GET", f"{P}/model/feature-importances"): (INSIGHT, "Faktor paling berpengaruh"),
    ("GET", f"{P}/model/sensitivity"): (INSIGHT, "Kepekaan prediksi terhadap jumlah porsi"),
    ("GET", f"{P}/model/evaluations"): (INSIGHT, "Evaluasi model: validasi silang, test, pembanding"),
    ("GET", f"{P}/model/tuning"): (INSIGHT, "Hasil optimasi hyperparameter"),
    ("GET", f"{P}/model/evaluation-predictions"): (INSIGHT, "Prediksi vs aktual pada data uji"),
    # 9. Laporan
    ("GET", f"{P}/reports/summary"): (LAPORAN, "Ringkasan limbah aktual per periode"),
    ("POST", f"{P}/report-exports"): (LAPORAN, "Buat file laporan PDF/Excel (opsional kirim email)"),
    ("GET", f"{P}/report-exports"): (LAPORAN, "Riwayat file laporan"),
    ("GET", f"{P}/report-exports/{{export_id}}"): (LAPORAN, "Detail file laporan"),
    ("GET", f"{P}/report-exports/{{export_id}}/file"): (LAPORAN, "Unduh file laporan"),
    ("GET", f"{P}/report-exports/{{export_id}}/email"): (LAPORAN, "Status pengiriman email laporan"),
    ("POST", f"{P}/report-exports/{{export_id}}/email/retry"): (LAPORAN, "Kirim ulang email yang gagal"),
    ("GET", f"{P}/model/evaluation-reports"): (LAPORAN, "Daftar laporan evaluasi model"),
    ("GET", f"{P}/model/evaluation-reports/{{report_id}}/file"): (
        LAPORAN,
        "Unduh laporan evaluasi model",
    ),
    # 10. Notifikasi
    ("GET", f"{P}/notifications"): (NOTIFIKASI, "Daftar notifikasi saya"),
    ("PATCH", f"{P}/notifications/{{notification_id}}/read"): (NOTIFIKASI, "Tandai notifikasi dibaca"),
    # 11. Model
    ("GET", f"{P}/model/active"): (MODEL, "Model aktif dan metriknya"),
    ("GET", f"{P}/model/versions"): (MODEL, "Semua versi model"),
    ("POST", f"{P}/model/reload"): (MODEL, "Muat ulang model dari HDFS (khusus pemilik)"),
    ("GET", f"{P}/training-exports"): (MODEL, "Riwayat ekspor data aktual (khusus pemilik)"),
    ("POST", f"{P}/training-exports"): (MODEL, "Ekspor data aktual ke HDFS sekarang (khusus pemilik)"),
}

# Swagger UI: grup tertutup, form langsung bisa diisi, ada kotak pencarian kelompok.
SWAGGER_UI = {
    "docExpansion": "none",
    "tryItOutEnabled": True,
    "displayRequestDuration": True,
    "defaultModelsExpandDepth": -1,
    "filter": True,
}

DESCRIPTION = """
Backend prediksi limbah makanan restoran: PostgreSQL (operational, prediction,
model_analysis) dan model Random Forest dari pipeline MLflow yang disimpan di HDFS.

**Cara mencoba fitur di halaman ini**

1. Buka kelompok **1. Akun dan login**, jalankan *Daftar akun* (atau *Masuk*).
   Cookie sesi tersimpan di browser.
2. Lanjutkan kelompok 2 sampai 11 sesuai urutan. Setiap form sudah berisi body contoh;
   ganti `id` dengan nilai dari respons sebelumnya bila diminta.
3. Klik **Execute**, lalu lihat *Response body* dan kodenya (200/201 berhasil,
   401 belum login, 403 butuh peran lain, 404 id salah, 409 data bentrok, 422 isian tidak valid).
"""


def install(app) -> None:
    """Pasang pengelompokan dan judul endpoint pada dokumen OpenAPI aplikasi."""
    base = app.openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = base()
        for path, operations in schema.get("paths", {}).items():
            for method, operation in operations.items():
                tag, summary = ROUTES.get((method.upper(), path), (None, None))
                if tag:
                    operation["tags"] = [tag]
                    operation["summary"] = summary
        schema["tags"] = TAGS
        return schema

    app.openapi = openapi
