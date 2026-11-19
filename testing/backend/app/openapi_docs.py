"""Penataan Swagger UI (/docs) untuk mencoba fitur FoodSave tanpa frontend.

Secara bawaan Swagger UI hanya menampilkan dua kelompok: Prediksi 7 Hari dan Simulasi Porsi.
Kelompok Login hanya tampil bila LOGIN_REQUIRED=true; tanpa login, semua aksi memakai akun uji
coba bawaan (app.services.accounts). Simulasi butuh satu rencana harian, jadi "Simpan input
harian" ikut tampil sebagai langkah pertamanya. Endpoint lain (input harian lengkap, dashboard, laporan, insight,
dan seterusnya) tetap berfungsi dan bisa ditampilkan dengan DOCS_SHOW_ALL=true.

Modul ini hanya mengubah dokumen OpenAPI; perilaku endpoint tidak berubah.
"""

import copy

LOGIN = "Login"
MINGGUAN = "1. Prediksi 7 Hari"
SIMULASI = "2. Simulasi Porsi"


def features(login_required: bool) -> list[str]:
    """Kelompok yang tampil secara bawaan; Login hanya bila login diwajibkan."""
    return ([LOGIN] if login_required else []) + [MINGGUAN, SIMULASI]


# Hanya tampil bila DOCS_SHOW_ALL=true.
INPUT = "Lainnya: Input Data Harian"
AKUN_TIM = "Lainnya: Akun dan tim"
PENGATURAN = "Lainnya: Pengaturan restoran"
UNGGAHAN = "Lainnya: Riwayat unggahan"
DASHBOARD = "Lainnya: Dashboard"
INSIGHT = "Lainnya: Insight & Penyebab"
LAPORAN = "Lainnya: Laporan"
NOTIFIKASI = "Lainnya: Notifikasi"
MODEL = "Lainnya: Model dan pelatihan ulang"
STATUS = "Lainnya: Status sistem"

LOGIN_WAJIB = (
    "Wajib sebelum mencoba fitur. Jalankan **Daftar akun** sekali (atau **Masuk** bila sudah punya "
    "akun). Browser menyimpan cookie sesi, jadi tidak perlu tombol Authorize."
)
LOGIN_OPSIONAL = (
    "Tidak wajib (LOGIN_REQUIRED=false): tanpa login, semua aksi memakai akun uji coba bawaan "
    "\"Restoran Uji Coba\". Login hanya bila ingin memakai akun sendiri."
)

TAGS = [
    {
        "name": LOGIN,
        "description": LOGIN_WAJIB,
    },
    {
        "name": MINGGUAN,
        "description": "Prediksi limbah tujuh hari sekaligus dari rencana porsi, staf, dan cuaca per "
        "hari. Body contoh berisi 23 sampai 29 November 2026. Untuk mengubah satu hari, salin `id` "
        "rencana (`plan_id`), lalu `id` (`day_id`) dan `version` hari itu dari respons Langkah 1; "
        "`operation_date` di body harus sama dengan tanggal hari itu.",
    },
    {
        "name": SIMULASI,
        "description": "Uji pengurangan porsi 0/5/10/15% dan jumlah staf untuk satu rencana harian. "
        "Langkah 1 menyimpan rencana harian (body contoh 19 November 2026); salin `id` dan `version` "
        "dari responsnya. Isi `daily_operation_id` di Langkah 2 dan 3 dengan `id` itu. Langkah 4 "
        "mengubah porsi dan staf pada rencana harian, mencatat koreksi, dan menyimpan prediksi baru; "
        "isi `expected_operation_version` dengan `version` saat ini.",
    },
    {
        "name": INPUT,
        "description": "Pratinjau, prediksi, koreksi, riwayat, dan unggah CSV/Excel (contoh file: "
        "`docs/contoh/daily_operations.csv`, jalankan `apply=false` lalu `apply=true`).",
    },
    {"name": AKUN_TIM, "description": "Profil, sesi login, dan tambah anggota tim."},
    {"name": PENGATURAN, "description": "Harga bahan per kg, batas risiko, kapasitas porsi."},
    {"name": UNGGAHAN, "description": "Riwayat dan file unggahan CSV/Excel."},
    {"name": DASHBOARD, "description": "Isi `on`/`end` dengan tanggal yang sudah punya input harian."},
    {"name": INSIGHT, "description": "Analisis model (statis dari MLflow) dan insight operasional."},
    {"name": LAPORAN, "description": "Ringkasan periode, file PDF/Excel, email ke Mailpit lokal."},
    {"name": NOTIFIKASI, "description": "Notifikasi muncul saat prediksi masuk kategori Tinggi."},
    {"name": MODEL, "description": "Model aktif, muat ulang dari HDFS, ekspor data aktual."},
    {"name": STATUS, "description": "Tidak butuh login."},
]

P = "/api/v1"
# Urutan di sini menentukan urutan tampil di Swagger UI.
ROUTES = {
    # Login (tampil hanya bila LOGIN_REQUIRED=true)
    ("POST", f"{P}/auth/register"): (LOGIN, "Daftar akun pemilik dan restoran baru (langsung login)"),
    ("POST", f"{P}/auth/login"): (LOGIN, "Masuk"),
    ("GET", f"{P}/auth/me"): (LOGIN, "Lihat akun yang sedang login"),
    ("POST", f"{P}/auth/logout"): (LOGIN, "Keluar"),
    # 1. Prediksi 7 Hari
    ("POST", f"{P}/weekly-predictions"): (MINGGUAN, "Langkah 1: buat rencana 7 hari (7 prediksi sekaligus)"),
    ("GET", f"{P}/weekly-predictions"): (MINGGUAN, "Daftar rencana"),
    ("GET", f"{P}/weekly-predictions/{{plan_id}}"): (MINGGUAN, "Langkah 2: lihat rencana dan prediksi per hari"),
    ("PUT", f"{P}/weekly-predictions/{{plan_id}}/days/{{day_id}}"): (
        MINGGUAN,
        "Langkah 3: ubah satu hari lalu prediksi ulang",
    ),
    ("GET", f"{P}/weekly-predictions/{{plan_id}}/revisions"): (MINGGUAN, "Langkah 4: riwayat revisi rencana"),
    # 2. Simulasi Porsi (Langkah 1 memakai endpoint input harian karena simulasi butuh rencana harian)
    ("POST", f"{P}/daily-operations"): (SIMULASI, "Langkah 1: simpan rencana harian yang akan disimulasikan"),
    ("GET", f"{P}/daily-operations/{{operation_id}}"): (SIMULASI, "Lihat rencana harian dan version-nya"),
    ("POST", f"{P}/portion-scenarios/options"): (
        SIMULASI,
        "Langkah 2: bandingkan pengurangan 0/5/10/15% (tanpa menyimpan)",
    ),
    ("POST", f"{P}/portion-scenarios"): (SIMULASI, "Langkah 3: simpan skenario"),
    ("GET", f"{P}/portion-scenarios"): (SIMULASI, "Daftar skenario"),
    ("POST", f"{P}/portion-scenarios/{{scenario_id}}/apply"): (
        SIMULASI,
        "Langkah 4: terapkan skenario ke rencana harian",
    ),
    ("GET", f"{P}/portion-scenarios/{{scenario_id}}"): (SIMULASI, "Detail skenario"),
    # Lainnya (DOCS_SHOW_ALL=true)
    ("POST", f"{P}/predictions/preview"): (INPUT, "Pratinjau prediksi tanpa menyimpan"),
    ("GET", f"{P}/daily-operations"): (INPUT, "Riwayat input harian"),
    ("POST", f"{P}/daily-operations/{{operation_id}}/predict"): (
        INPUT,
        "Jalankan dan simpan prediksi untuk input harian",
    ),
    ("PUT", f"{P}/daily-operations/{{operation_id}}"): (INPUT, "Koreksi input harian"),
    ("GET", f"{P}/daily-operations/{{operation_id}}/corrections"): (INPUT, "Riwayat koreksi input"),
    ("POST", f"{P}/imports"): (INPUT, "Unggah CSV/Excel (apply=false periksa, apply=true simpan)"),
    ("GET", f"{P}/predictions"): (INPUT, "Riwayat hasil prediksi"),
    ("GET", f"{P}/predictions/{{prediction_id}}"): (INPUT, "Detail satu hasil prediksi"),
    ("PUT", f"{P}/auth/me"): (AKUN_TIM, "Ubah nama dan preferensi notifikasi"),
    ("GET", f"{P}/auth/sessions"): (AKUN_TIM, "Daftar sesi login"),
    ("DELETE", f"{P}/auth/sessions/{{session_id}}"): (AKUN_TIM, "Akhiri satu sesi login"),
    ("POST", f"{P}/auth/users"): (AKUN_TIM, "Tambah manager atau staf (khusus pemilik)"),
    ("GET", f"{P}/restaurant"): (PENGATURAN, "Lihat restoran"),
    ("PUT", f"{P}/restaurant"): (PENGATURAN, "Ubah nama restoran"),
    ("GET", f"{P}/users"): (PENGATURAN, "Daftar anggota tim"),
    ("GET", f"{P}/settings"): (PENGATURAN, "Lihat harga bahan dan batas risiko"),
    ("PUT", f"{P}/settings"): (PENGATURAN, "Ubah harga bahan, batas risiko, dan kapasitas"),
    ("GET", f"{P}/imports"): (UNGGAHAN, "Riwayat unggahan"),
    ("GET", f"{P}/imports/{{import_id}}"): (UNGGAHAN, "Detail hasil pemeriksaan unggahan"),
    ("GET", f"{P}/imports/{{import_id}}/file"): (UNGGAHAN, "Unduh file yang diunggah"),
    ("GET", f"{P}/dashboard"): (DASHBOARD, "Ringkasan satu tanggal: input, prediksi, risiko"),
    ("GET", f"{P}/dashboard/trend"): (DASHBOARD, "Aktual vs prediksi per tanggal"),
    ("GET", f"{P}/insights/operational"): (INSIGHT, "Beban staf dan limbah per kategori"),
    ("GET", f"{P}/model/feature-importances"): (INSIGHT, "Faktor paling berpengaruh"),
    ("GET", f"{P}/model/sensitivity"): (INSIGHT, "Kepekaan prediksi terhadap jumlah porsi"),
    ("GET", f"{P}/model/evaluations"): (INSIGHT, "Evaluasi model: validasi silang, test, pembanding"),
    ("GET", f"{P}/model/tuning"): (INSIGHT, "Hasil optimasi hyperparameter"),
    ("GET", f"{P}/model/evaluation-predictions"): (INSIGHT, "Prediksi vs aktual pada data uji"),
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
    ("GET", f"{P}/notifications"): (NOTIFIKASI, "Daftar notifikasi saya"),
    ("PATCH", f"{P}/notifications/{{notification_id}}/read"): (NOTIFIKASI, "Tandai notifikasi dibaca"),
    ("GET", f"{P}/model/active"): (MODEL, "Model aktif dan metriknya"),
    ("GET", f"{P}/model/versions"): (MODEL, "Semua versi model"),
    ("POST", f"{P}/model/reload"): (MODEL, "Muat ulang model dari HDFS (khusus pemilik)"),
    ("GET", f"{P}/training-exports"): (MODEL, "Riwayat ekspor data aktual (khusus pemilik)"),
    ("POST", f"{P}/training-exports"): (MODEL, "Ekspor data aktual ke HDFS sekarang (khusus pemilik)"),
    ("GET", "/health/live"): (STATUS, "Cek API hidup"),
    ("GET", "/health/ready"): (STATUS, "Cek kesiapan: database, HDFS, model aktif"),
}

# Swagger UI: daftar endpoint langsung terlihat, form langsung bisa diisi, ada kotak pencarian.
SWAGGER_UI = {
    "docExpansion": "list",
    "tryItOutEnabled": True,
    "displayRequestDuration": True,
    "defaultModelsExpandDepth": -1,
    "filter": True,
}

def description(login_required: bool) -> str:
    """Teks pembuka Swagger UI sesuai mode login."""
    if login_required:
        start = (
            "1. Buka **Login**, jalankan *Daftar akun* (atau *Masuk*). Cookie sesi tersimpan di browser.\n"
            "2. Coba **1. Prediksi 7 Hari** dan **2. Simulasi Porsi**, ikuti Langkah 1 sampai 4."
        )
        codes = "401 belum login, "
    else:
        start = (
            "1. Tidak perlu login: semua aksi memakai akun uji coba bawaan \"Restoran Uji Coba\".\n"
            "2. Coba **1. Prediksi 7 Hari** dan **2. Simulasi Porsi**, ikuti Langkah 1 sampai 4."
        )
        codes = ""
    return f"""
Uji coba fitur Prediksi 7 Hari dan Simulasi Porsi FoodSave. Prediksi dihitung model Random
Forest dari pipeline MLflow yang disimpan di HDFS.

**Cara mencoba fitur di halaman ini**

{start}
   Setiap form sudah berisi body contoh; ganti `id` dengan nilai dari respons sebelumnya
   bila diminta.
3. Klik **Execute**, lalu lihat *Response body* dan kodenya (200/201 berhasil,
   {codes}404 id salah, 409 data bentrok, 422 isian tidak valid).
"""


def arrange(schema: dict, show_all: bool = False, login_required: bool = True) -> dict:
    """Salinan dokumen OpenAPI yang sudah dikelompokkan, diurutkan, dan (bawaan) disaring."""
    schema = copy.deepcopy(schema)
    order = list(dict.fromkeys(path for _, path in ROUTES))
    paths = schema.get("paths", {})
    ordered = {p: paths[p] for p in order if p in paths}
    ordered.update({p: v for p, v in paths.items() if p not in ordered})
    result = {}
    for path, operations in ordered.items():
        kept = {}
        for method, operation in operations.items():
            tag, summary = ROUTES.get((method.upper(), path), (None, None))
            if tag:
                operation["tags"] = [tag]
                operation["summary"] = summary
            if show_all or tag in features(login_required):
                kept[method] = operation
        if kept:
            result[path] = kept
    schema["paths"] = result
    used = {op["tags"][0] for ops in result.values() for op in ops.values() if op.get("tags")}
    tags = copy.deepcopy([t for t in TAGS if t["name"] in used])
    for tag in tags:
        if tag["name"] == LOGIN and not login_required:
            tag["description"] = LOGIN_OPSIONAL
    schema["tags"] = tags
    schema["info"]["description"] = description(login_required)
    return schema


def install(app, show_all: bool = False, login_required: bool = True) -> None:
    """Pasang penataan Swagger UI pada aplikasi FastAPI."""
    base = app.openapi

    def openapi():
        if getattr(app, "_foodsave_openapi", None) is None:
            app._foodsave_openapi = arrange(base(), show_all, login_required)
        return app._foodsave_openapi

    app.openapi = openapi
