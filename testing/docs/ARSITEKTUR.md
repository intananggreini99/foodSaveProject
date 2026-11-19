# Arsitektur Sistem FoodSave (backend v2)

Dokumen ini memetakan diagram *Arsitektur Sistem FoodSave* ke kode dan layanan Docker.

## 1. Komponen

| Komponen di diagram | Layanan Compose | Kode |
|---|---|---|
| Pengguna → Swagger UI FastAPI (`/docs`); frontend belum dipasang | `api` | `backend/app/openapi_docs.py` (kelompok dan judul endpoint), contoh body di `backend/app/schemas.py` |
| FastAPI: API /api/v1 | `api` | `backend/app/routers/` |
| FastAPI: layanan prediksi (model .pkl di memori) | `api` | `backend/app/services/prediction_service.py` |
| FastAPI: pekerja laporan (PDF, XLSX, email) | `api` (buat file), `report-worker` (email) | `backend/app/services/report_files.py`, `backend/app/workers/report_worker.py` |
| PostgreSQL: 1 database `foodsave`, 3 skema | `postgres`, `migrate` | `backend/app/models/`, `backend/migrations/` |
| Apache Hadoop HDFS (image bde2020, sama dengan SatisView) | `namenode`, `datanode`, `hdfs-init` | `shared/foodsave_core/storage.py`, `infra/hadoop/hadoop.env` |
| MLflow: 6 langkah pipeline | `trainer-init`, `trainer` | `ml/foodsave_ml/steps.py` |
| MLflow tracking | `mlflow` (database `mlflow` dibuat service `migrate`) | `infra/mlflow/`, `backend/app/tools/ensure_databases.py` |
| Aliran balik data aktual (garis hijau) | `exporter` | `backend/app/services/training_export.py` |
| Registrasi model (garis ungu) | langkah 6 pipeline | `ml/foodsave_ml/register.py` |

`shared/foodsave_core` dipasang di image backend **dan** image ml. Kelas `FoodPreprocessor`
di dalam `data_preprocessing.pkl` berasal dari modul ini, sehingga file yang ditulis MLflow
selalu bisa dibuka FastAPI. Versi numpy, pandas, scikit-learn, dan joblib dikunci sama di
`backend/requirements.txt` dan `ml/requirements.txt`.

## 2. Tata letak HDFS

```
/foodsave/raw/train.csv                         data mentah awal (diunggah hdfs-init)
/foodsave/raw/actuals/actuals_<waktu>.csv       ekspor data aktual dari aplikasi
/foodsave/processed/<versi>/data_bersih.csv     hasil langkah data_preprocessing
/foodsave/models/<versi>/data_preprocessing.pkl
/foodsave/models/<versi>/model_rf_optimize.pkl
/foodsave/models/<versi>/manifest.json
/foodsave/reports/evaluasi/<versi>/laporan_evaluasi.xlsx | .pdf
```

FastAPI dan pipeline mengakses HDFS lewat REST WebHDFS (port 9870), tanpa libhdfs/Java di
image aplikasi. Untuk pengembangan dan tes, `FOODSAVE_STORAGE=local` memakai folder dengan
struktur path yang sama.

File unggahan CSV dan laporan operasional milik restoran disimpan di volume `app_storage`
milik FastAPI, bukan di HDFS: HDFS hanya untuk data pelatihan dan artefak model.

## 3. Pipeline MLflow (enam langkah)

| # | Langkah | Yang dilakukan | Hasil |
|---|---|---|---|
| 1 | `data_preprocessing` | Baca `train.csv` + semua ekspor aktual dari HDFS, buang baris tanpa tanggal/target valid, hapus duplikat (ekspor terbaru per operasi menang), bagi menurut waktu: 80% tanggal awal = latih/validasi, 20% tanggal terakhir = test | `processed/<versi>/data_bersih.csv` |
| 2 | `train rf_model` | Konfigurasi dasar dinilai dengan validasi silang berurutan waktu (TimeSeriesSplit, preprocessing di-fit ulang per lipatan) | trial 0 |
| 3 | `optimasi parameter rf_model` | Coba kombinasi parameter; pilih MAE CV terkecil (seri: RMSE) | trial 1..n, parameter terbaik |
| 4 | `analisis data model_rf_optimize` | Latih pada 80% awal, uji **sekali** pada 20% terakhir: MAE, MSE, RMSE, MAPE, R², pembanding median, rentang ±kg dari residual validasi, faktor berpengaruh (permutasi) | `reports/evaluasi/<versi>/` XLSX + PDF |
| 5 | `create file .pkl` | Latih ulang preprocessing + model dengan **semua** data memakai parameter terbaik; hitung kurva kepekaan porsi | `models/<versi>/*.pkl`, `manifest.json` |
| 6 | `register model` | Daftarkan ke MLflow Model Registry (alias `aktif`) dan isi skema `model_analysis`; versi lama dinonaktifkan | baris baru di `model_versions` |

Data test tidak pernah dipakai memilih parameter. Metrik yang ditampilkan aplikasi selalu
dari langkah 4, walaupun file .pkl produksi dilatih ulang dengan semua data di langkah 5.

Satu run induk MLflow berisi enam run anak dengan nama langkah di atas; setiap trial
optimasi menjadi run anak tersendiri.

## 4. Database `foodsave`

### Skema `operational` (data operasional)
`restaurants`, `users`, `user_sessions`, `restaurant_settings`, `daily_operations`,
`data_corrections`, `data_imports`, `notifications`, `report_exports`, `email_deliveries`,
`email_attempts`, `training_exports` (baru).

### Skema `prediction` (hasil prediksi realtime)
`prediction_results`, `weekly_predictions`, `prediction_days`, `plan_revisions`,
`portion_scenarios`, `inference_logs` (baru: satu baris per panggilan model).

### Skema `model_analysis` (data statis dari MLflow)
`model_versions`, `dataset_versions`, `training_runs`, `tuning_trials`, `model_evaluations`,
`evaluation_predictions`, `feature_importances`, `sensitivity_curves`, `evaluation_reports`.

Ketiga skema berada di satu database agar foreign key lintas skema dan transaksi tunggal
tetap berlaku, misalnya: kunci `daily_operations` → simpan `prediction_results` → buat
`notifications` dalam satu commit. Hanya boleh ada satu baris `model_versions.is_active`
(indeks unik parsial).

## 5. Fitur → jenis data → endpoint

Swagger UI (`/docs`) secara bawaan hanya menampilkan Prediksi 7 Hari dan Simulasi Porsi
(ditambah *Simpan input harian* sebagai langkah pertama simulasi); endpoint lain tetap aktif dan
tampil bila `DOCS_SHOW_ALL=true`. Dengan `LOGIN_REQUIRED=false` (bawaan rilis lokal) permintaan
tanpa sesi login memakai akun uji coba bawaan "Restoran Uji Coba"; dengan `true`, kelompok Login
ikut tampil dan semua endpoint fitur mewajibkan login. Kolom "Fitur"
memakai nama halaman frontend yang direncanakan.

| Fitur | Jenis | Endpoint utama |
|---|---|---|
| Masuk / Daftar | operasional | `/auth/register`, `/auth/login`, `/auth/me` |
| Dashboard | operasional (prediksi tersimpan) | `GET /dashboard?on=`, `GET /dashboard/trend` |
| Input Data Harian | **realtime** | `POST /daily-operations`, `POST /predictions/preview`, `POST /daily-operations/{id}/predict` |
| Input: unggah CSV | operasional (tanpa model) | `POST /imports?apply=true` |
| Prediksi 7 Hari | **realtime** (7 baris, 1 panggilan) | `POST /weekly-predictions`, `PUT /weekly-predictions/{id}/days/{day}` |
| Simulasi Porsi | **realtime** | `POST /portion-scenarios/options` (5 baris), `POST /portion-scenarios`, `POST .../apply` |
| Insight & Penyebab | statis + operasional | `GET /model/feature-importances`, `/model/evaluations`, `/model/sensitivity`, `/insights/operational` |
| Laporan | operasional | `GET /reports/summary`, `POST /report-exports`, email |
| Laporan evaluasi model | statis (HDFS) | `GET /model/evaluation-reports`, `.../{id}/file` |
| Notifikasi | operasional | `GET /notifications`, `PATCH /notifications/{id}/read` |
| Pengaturan | operasional + statis | `/settings`, `/restaurant`, `/users`, `GET /model/active` |

Semua endpoint berawalan `/api/v1`. Dokumentasi interaktif: `/docs`.

## 6. Layanan prediksi

1. Baca `model_analysis.model_versions` yang aktif.
2. Bila versi itu belum ada di memori: unduh kedua file .pkl dari HDFS, cocokkan SHA-256
   dengan catatan database, `joblib.load`, cek jumlah fitur.
3. Prediksi memakai model di memori. Ganti versi aktif = model baru dimuat pada
   permintaan berikutnya; `POST /model/reload` (pemilik) memaksa muat ulang.
4. Setiap panggilan dicatat di `prediction.inference_logs` (jumlah baris, durasi, sukses/gagal).

Model hanya memakai tujuh isian rencana: tanggal, porsi, staf, pengalaman staf, acara
khusus, suhu, kelembapan. `actual_waste_kg`, `waste_category`, dan `previous_waste_kg`
tidak pernah masuk ke model. Prediksi dengan isian di luar rentang data latih ditandai
`outside_training_range`.

## 7. Aliran balik data aktual

`exporter` (default tiap 24 jam) atau `POST /training-exports` (pemilik) menulis input harian
yang sudah punya limbah aktual dan berubah sejak ekspor terakhir ke
`/foodsave/raw/actuals/`, dalam format kolom yang sama dengan `train.csv`. Pelatihan ulang
berikutnya otomatis membaca file tersebut.

Privasi: data aktual satu restoran ikut melatih model bersama, tetapi tidak pernah dibuka
per tanggal ke restoran lain. Endpoint `evaluation-predictions` hanya mengembalikan baris
dari dataset publik awal; catatan ekspor tidak memuat isi data.

## 8. Keandalan

| Gangguan | Perilaku |
|---|---|
| PostgreSQL mati sementara | Endpoint menjawab 503 "Database tidak dapat dihubungi" (+ `Retry-After`), `/health/live` tetap 200, koneksi pulih sendiri saat database hidup lagi. |
| HDFS mati | Prediksi tetap jalan memakai model di memori; `/health/ready` 503; `POST /model/reload` gagal tanpa membuang model lama. |
| HDFS belum siap saat start | `hdfs-init` menunggu datanode terdaftar dan safemode mati (JMX namenode), unggahan diulang beberapa kali. |
| File .pkl berubah/rusak | Ditolak karena SHA-256 tidak cocok dengan `model_versions`; API menjawab 503, model tidak dimuat. |
| Error tak terduga | JSON `{"detail", "error_id"}` tanpa detail internal; jejak lengkap ada di log dengan `error_id` yang sama. |

Kinerja (2 proses uvicorn, laptop 2 inti): 80 pratinjau prediksi dengan 8 permintaan
bersamaan, median 161 ms, p95 267 ms. Model dimuat dengan `n_jobs=1` untuk inferensi karena
3x lebih cepat untuk beberapa baris.

## 9. Batasan yang perlu diketahui

- Rilis ditujukan untuk satu laptop (localhost): port hanya terbuka di `127.0.0.1`, cookie
  sesi tanpa flag `Secure` karena tidak memakai HTTPS, dan email hanya ke Mailpit lokal.
- `LOGIN_REQUIRED=false` (bawaan rilis lokal) membuat API bisa dipakai tanpa login lewat akun
  uji coba bawaan. Wajib diubah ke `true` sebelum API dibuka untuk orang lain.
  Untuk deploy ke server diperlukan HTTPS, domain, SMTP sungguhan, dan backup terjadwal.
- Dataset tidak memiliki ID restoran; data publik awal dianggap satu sumber gabungan.
- Rentang estimasi ±kg adalah kuantil 90% error validasi, bukan jaminan statistik.
- Compose divalidasi dengan `docker compose config`. Uji end-to-end dijalankan dengan
  PostgreSQL, server MLflow, FastAPI (uvicorn), pekerja laporan, dan SMTP sungguhan, serta
  WebHDFS tiruan lewat jaringan (namenode + datanode dengan redirect 307 dan JMX). Kontainer
  Hadoop bde2020 sendiri baru teruji di laptop Anda (dipakai SatisView).
- Perintah backup dan pulihkan di README diuji dengan PowerShell 7 dan perintah `docker`
  tiruan. Pemulihan SQL diuji dengan PostgreSQL sungguhan. Salin HDFS memakai
  `hdfs dfs -get/-put` di container namenode, jadi cobalah sekali backup lalu pulihkan
  sebelum data sungguhan menumpuk.
