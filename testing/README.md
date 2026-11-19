# FoodSave Restaurant

Prediksi limbah makanan harian restoran (kg) dan simulasi pengurangan porsi, dengan model
Random Forest yang dilatih ulang lewat pipeline MLflow dan disajikan oleh FastAPI.

## Arsitektur

```
Pengguna ─▶ Swagger UI (/docs) ◀──REST──▶ FastAPI ◀──▶ PostgreSQL "foodsave"
                                             │  API /api/v1       ├─ operational
                                             │  pekerja laporan    ├─ prediction
                                             │  layanan prediksi   └─ model_analysis
                                             │        ▲ muat .pkl versi aktif
                                             ▼        │
   ekspor data aktual ──────────────────▶ Apache Hadoop HDFS ◀──────── MLflow (6 langkah)
                                          raw / processed / models /   tracking: database "mlflow"
                                          reports/evaluasi
```

Penjelasan lengkap per komponen, aliran data, tabel, dan endpoint ada di
[docs/ARSITEKTUR.md](docs/ARSITEKTUR.md).

## Struktur folder

```
├── compose.yaml          semua layanan (PostgreSQL, HDFS, MLflow, FastAPI, pekerja, Mailpit)
├── .env.example          contoh konfigurasi
├── backend/              FastAPI: app/ (routers, services, workers), migrations/, tests/
├── ml/                   pipeline MLflow: foodsave_ml/ (6 langkah), tests/
├── shared/               paket foodsave_core: preprocessing + akses HDFS (dipakai backend & ml)
├── infra/                konfigurasi Hadoop (bde2020) dan image MLflow
├── dataset/raw/train.csv data mentah awal (diunggah ke HDFS saat start)
├── docs/                 dokumentasi arsitektur, contoh/daily_operations.csv untuk uji unggah
└── research/             arsip riset lama (notebook, perbandingan 4 model); tidak dipakai runtime
```

## Rilis lokal di laptop (localhost)

Proyek ini dirilis untuk dipakai di laptop sendiri, bukan untuk deploy ke server atau
internet. Belum ada frontend: semua fitur dicoba lewat Swagger UI FastAPI di
http://localhost:8010/docs. Semua port hanya terbuka di `127.0.0.1`, sehingga perangkat lain di jaringan
Wi-Fi yang sama pun tidak bisa mengaksesnya. Yang dibutuhkan hanya Docker Desktop.

Semua perintah di bawah diketik satu per satu di PowerShell. Tunggu satu perintah selesai
tanpa error sebelum menjalankan perintah berikutnya.

### Langkah 1: siapkan `.env` (sekali saja)

```powershell
cd D:\ProjectSistemCerdas\foodSaveProject
Copy-Item .env.example .env
notepad .env
```

Di Notepad, ganti nilai `POSTGRES_PASSWORD` (huruf dan angka saja), simpan, lalu tutup.

### Langkah 2: cek port tidak bentrok

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8010,5434,5010,9871,8026 -ErrorAction SilentlyContinue
```

Tidak ada keluaran berarti semua port bebas. Bila muncul baris, lihat container mana yang
memakai port tersebut:

```powershell
docker ps --format "{{.Names}}  {{.Ports}}"
```

Lalu ganti port yang bentrok di `.env` (variabel `FOODSAVE_*_PORT`; bila mengganti
`FOODSAVE_API_PORT`, sesuaikan juga `CORS_ORIGINS`) dan cek lagi dengan nomor port baru.
Bila FoodSave sedang menyala, port-port tersebut memang dipakai Docker (proses
`com.docker.backend` atau `wslrelay`); itu normal.

Windows juga bisa mencadangkan rentang port untuk Hyper-V/WSL. Port FoodSave tidak boleh
berada di salah satu rentang yang tampil di sini:

```powershell
netsh interface ipv4 show excludedportrange protocol=tcp
```

### Langkah 3: build dan nyalakan semua layanan

```powershell
docker compose up -d --build
```

Start pertama ±5–10 menit (unduh image, build, lalu pelatihan model awal).

### Langkah 4: tunggu sampai siap

```powershell
docker compose ps
docker compose logs -f trainer-init
```

Tekan Ctrl+C setelah log pelatihan selesai; layanan tetap berjalan. Lalu cek:

```powershell
curl.exe -s http://localhost:8010/health/ready
```

Sistem siap bila hasilnya memuat `"status":"ready"`. Pakai `curl.exe`, bukan `curl`, karena
di Windows PowerShell `curl` adalah nama lain `Invoke-WebRequest`.

### Langkah 5: buka Swagger UI

```powershell
Start-Process http://localhost:8010/docs
```

Lanjutkan dengan panduan [Mencoba fitur lewat Swagger UI](#mencoba-fitur-lewat-swagger-ui).

### Pemakaian sehari-hari

| Keperluan | Perintah |
|---|---|
| Nyalakan | `docker compose up -d` |
| Cek siap | `curl.exe -s http://localhost:8010/health/ready` |
| Status semua layanan | `docker compose ps` |
| Log satu layanan | `docker compose logs -f api` (Ctrl+C untuk keluar) |
| Matikan (data tetap tersimpan) | `docker compose stop` |
| Setelah kode diubah | `docker compose up -d --build` |

Layanan **tidak** menyala sendiri saat laptop dihidupkan. Jalankan `docker compose up -d`
dari folder proyek setiap kali ingin memakai aplikasi. Bila sebuah layanan crash, Docker
mencoba menyalakannya ulang paling banyak 5 kali.

### Lokasi data

Data disimpan di volume Docker di laptop ini, bukan di folder proyek:

| Volume | Isi |
|---|---|
| `foodsave_postgres_data` | database `foodsave` (3 skema) dan `mlflow` |
| `foodsave_hdfs_namenode`, `foodsave_hdfs_datanode` | HDFS: data mentah, data aktual, file `.pkl`, laporan evaluasi |
| `foodsave_mlflow_artifacts` | artefak MLflow |
| `foodsave_app_storage` | file unggahan dan laporan operasional |
| `foodsave_mailpit_data` | email uji di Mailpit |

Data tetap ada setelah `docker compose stop`, `docker compose down`, atau restart laptop.
Data **terhapus** bila menjalankan `docker compose down -v` atau menghapus volume dari
Docker Desktop, jadi backup lebih dulu.

### Backup data

FoodSave harus sedang menyala. Jalankan semua perintah di **jendela PowerShell yang sama**,
karena perintah memakai variabel `$folder`. Bila `POSTGRES_USER` di `.env` diubah, ganti
`foodsave` setelah `-U` dengan nama tersebut.

Buat folder backup:

```powershell
$folder = "backup\" + (Get-Date -Format "yyyyMMdd-HHmmss")
New-Item -ItemType Directory -Path $folder
```

Database aplikasi dan MLflow. `pg_dump` menulis file di dalam container lalu disalin,
karena `pg_dump > file` di Windows PowerShell menyimpan file sebagai UTF-16 yang tidak bisa
dipulihkan:

```powershell
docker compose exec -T postgres pg_dump -U foodsave -d foodsave --no-owner -f /tmp/foodsave.sql
docker compose cp postgres:/tmp/foodsave.sql "$folder\foodsave.sql"
docker compose exec -T postgres pg_dump -U foodsave -d mlflow --no-owner -f /tmp/mlflow.sql
docker compose cp postgres:/tmp/mlflow.sql "$folder\mlflow.sql"
docker compose exec -T postgres rm -f /tmp/foodsave.sql /tmp/mlflow.sql
```

HDFS (data mentah, data aktual, file `.pkl`, laporan evaluasi):

```powershell
docker compose exec -T namenode sh -c "rm -rf /tmp/hdfs_backup && hdfs dfs -get /foodsave /tmp/hdfs_backup"
docker compose cp namenode:/tmp/hdfs_backup "$folder\hdfs"
docker compose exec -T namenode rm -rf /tmp/hdfs_backup
```

Artefak MLflow dan file aplikasi:

```powershell
docker compose cp mlflow:/mlflow/artifacts "$folder\mlflow-artifacts"
docker compose cp api:/app/storage "$folder\app-storage"
```

Periksa isinya. Harus ada `foodsave.sql`, `mlflow.sql`, `hdfs`, `mlflow-artifacts`, dan
`app-storage`:

```powershell
Get-ChildItem $folder
```

Folder `backup\` tidak ikut ke git. Isi Mailpit tidak ikut di-backup.

### Pulihkan dari backup

Data FoodSave saat ini **diganti** isi backup. Cara ini juga berlaku untuk instalasi baru
atau setelah `docker compose down -v`: jalankan Langkah 1–4 sampai siap, lalu perintah di
bawah. Model aktif dari backup langsung dipakai lagi karena file `.pkl` dan checksum-nya ikut
dipulihkan. Jalankan semua perintah di jendela PowerShell yang sama.

Pilih folder backup (ganti nama folder dengan salah satu hasil `Get-ChildItem backup`):

```powershell
Get-ChildItem backup
$folder = "backup\20261118-203000"
```

File aplikasi dan artefak MLflow, disalin selagi layanan `api` dan `mlflow` menyala:

```powershell
docker compose cp "$folder\app-storage\." api:/app/storage
docker compose cp "$folder\mlflow-artifacts\." mlflow:/mlflow/artifacts
docker compose exec -T -u root api chown -R foodsave:foodsave /app/storage
docker compose exec -T -u root mlflow chown -R mlflow /mlflow/artifacts
```

Hentikan layanan yang memakai database:

```powershell
docker compose stop mlflow api report-worker exporter
```

Database aplikasi:

```powershell
docker compose exec -T postgres psql -U foodsave -d postgres -c "DROP DATABASE IF EXISTS foodsave WITH (FORCE)" -c "CREATE DATABASE foodsave OWNER foodsave"
docker compose cp "$folder\foodsave.sql" postgres:/tmp/foodsave.sql
docker compose exec -T postgres psql -U foodsave -d foodsave -v ON_ERROR_STOP=1 -q -f /tmp/foodsave.sql
```

Database MLflow:

```powershell
docker compose exec -T postgres psql -U foodsave -d postgres -c "DROP DATABASE IF EXISTS mlflow WITH (FORCE)" -c "CREATE DATABASE mlflow OWNER foodsave"
docker compose cp "$folder\mlflow.sql" postgres:/tmp/mlflow.sql
docker compose exec -T postgres psql -U foodsave -d mlflow -v ON_ERROR_STOP=1 -q -f /tmp/mlflow.sql
docker compose exec -T postgres rm -f /tmp/foodsave.sql /tmp/mlflow.sql
```

HDFS (isi `/foodsave` diganti isi backup):

```powershell
docker compose exec -T namenode rm -rf /tmp/hdfs_restore
docker compose cp "$folder\hdfs" namenode:/tmp/hdfs_restore
docker compose exec -T namenode sh -c "hdfs dfs -rm -r -f -skipTrash /foodsave && hdfs dfs -put /tmp/hdfs_restore /foodsave && rm -rf /tmp/hdfs_restore"
```

Nyalakan lagi lalu cek:

```powershell
docker compose start mlflow api report-worker exporter
curl.exe -s http://localhost:8010/health/ready
```

Bila salah satu perintah gagal di tengah jalan, layanan yang dihentikan tadi belum menyala.
Perbaiki masalahnya lalu ulangi pemulihan dari awal, atau nyalakan dulu dengan
`docker compose up -d`.

### Hapus semua data (tidak bisa dibatalkan)

```powershell
docker compose down -v
```

### Detail start

Urutan start otomatis: PostgreSQL → database `mlflow` + migrasi 3 skema → HDFS (namenode,
datanode) → menunggu datanode hidup dan safemode mati → unggah `train.csv` ke HDFS → server
MLflow → **pelatihan awal** (hanya bila belum ada model aktif, ±1 menit) → FastAPI dan pekerja.

Port host dibuat berbeda dari project lain di laptop yang sama (SatisView memakai 3000, 5433,
8080, 9870; CampusFlow memakai 8081, 8088). Semua bisa diubah lewat `FOODSAVE_*_PORT` di `.env`.

| Layanan | Alamat |
|---|---|
| API + dokumentasi | http://localhost:8010/docs |
| Status siap | http://localhost:8010/health/ready |
| MLflow | http://localhost:5010 |
| HDFS (namenode) | http://localhost:9871 |
| Mailpit | http://localhost:8026 |
| PostgreSQL | localhost:5434 |

Image Hadoop sama dengan project SatisView (`bde2020/hadoop-*:2.0.0-hadoop3.2.1-java8`),
jadi tidak perlu diunduh ulang bila SatisView sudah pernah dijalankan. Kedua project memakai
kluster HDFS dan jaringan Docker masing-masing.

Uji seluruh sistem setelah semua layanan hidup (membuat restoran uji, menjalankan alur
setiap halaman, uji beban, lalu menghapus data uji):

```powershell
docker compose exec api python -m app.tools.uji_sistem
```

Pelatihan ulang (misalnya setelah data aktual baru diekspor ke HDFS):

```powershell
docker compose run --rm trainer                      # versi baru langsung aktif
docker compose run --rm trainer python -m foodsave_ml.pipeline --no-activate   # tanpa mengaktifkan
```

FastAPI memuat versi baru otomatis pada permintaan prediksi berikutnya.

### Mencoba fitur lewat Swagger UI

Buka http://localhost:8010/docs. Swagger UI hanya menampilkan dua kelompok: Prediksi 7 Hari
dan Simulasi Porsi, diberi nomor sesuai urutan mencoba. **Tidak perlu login**: semua aksi
memakai akun uji coba bawaan "Restoran Uji Coba", yang dibuat otomatis pada aksi pertama.
Setiap form sudah berisi body contoh yang valid; cukup klik **Execute**, lalu lihat
**Response body** dan kodenya. Ganti nilai `id` dengan nilai dari respons sebelumnya bila diminta.

| Kelompok | Urutan mencoba | Yang perlu diisi |
|---|---|---|
| 1. Prediksi 7 Hari | Langkah 1 *buat rencana 7 hari* → Langkah 2 *lihat rencana* → Langkah 3 *ubah satu hari lalu prediksi ulang* → Langkah 4 *riwayat revisi* | `plan_id` = `id` rencana; `day_id` dan `version` = `id` dan `version` hari ke-6 di `days` (body ubah hari sudah berisi tanggalnya, `2026-11-28`) |
| 2. Simulasi Porsi | Langkah 1 *simpan rencana harian* (salin `id` dan `version`) → Langkah 2 *bandingkan pengurangan 0/5/10/15%* → Langkah 3 *simpan skenario* (salin `id`) → Langkah 4 *terapkan skenario* | `daily_operation_id` = `id` rencana harian; `scenario_id` = `id` skenario; `expected_operation_version` = `version` rencana harian saat ini |

Kode respons: 200/201 berhasil, 404 `id` salah, 409 data bentrok (mis. tanggal sudah ada atau `version` sudah berubah),
422 isian tidak valid (lihat `detail` untuk kolom yang salah).

Body contoh memakai tanggal 19 November 2026 untuk rencana harian simulasi dan 23–29 November
2026 untuk rencana 7 hari. Menyimpan rencana harian dengan tanggal yang sama dua kali sengaja
ditolak (409); ganti `operation_date` untuk simulasi berikutnya. Mengubah hari rencana 7 hari
dengan `version` lama juga ditolak (409); pakai `version` dari respons terakhir.

Endpoint fitur lain (input harian lengkap, unggah CSV, dashboard, laporan, insight,
pengaturan, notifikasi, model) tidak dihapus, hanya disembunyikan dari `/docs`. Untuk menampilkannya, isi `DOCS_SHOW_ALL=true` di
`.env`, lalu `docker compose up -d`.

Swagger UI mengirim POST/PUT dari alamat http://localhost:8010, jadi alamat itu harus ada di
`CORS_ORIGINS` pada `.env` (bawaan `.env.example` sudah benar).

Mode tanpa login diatur oleh `LOGIN_REQUIRED` (bawaan `false` di `.env.example` dan
`compose.yaml`). Mode ini hanya untuk uji coba di laptop: siapa pun yang membuka
http://localhost:8010 memakai data "Restoran Uji Coba". Untuk mewajibkan daftar/masuk lagi,
isi `LOGIN_REQUIRED=true` di `.env` lalu `docker compose up -d`; kelompok **Login** akan
muncul di `/docs`. Bila browser masih menyimpan sesi login dari percobaan sebelumnya, aksi
memakai akun itu, bukan akun uji coba.

### Bila ada masalah

| Gejala | Penyebab dan solusi |
|---|---|
| `Bind for 0.0.0.0:XXXX failed: port is already allocated` | Port dipakai project lain. Cek seperti Langkah 2, ubah `FOODSAVE_*_PORT` di `.env`, lalu `docker compose up -d`. |
| `pull access denied for foodsave-...` | Compose versi lama. Pastikan memakai `compose.yaml` terbaru (setiap image lokal punya `build` dan `pull_policy: build`). |
| `hdfs-init` lama menunggu | Lihat `docker compose logs hdfs-init namenode datanode`. Pesan "Menunggu HDFS siap" normal selama datanode belum terdaftar (biasanya < 1 menit). |
| `/health/ready` 503 "Belum ada model aktif" | Pelatihan awal belum selesai. Pantau `docker compose logs -f trainer-init`. |
| Swagger tidak terbuka / `ERR_CONNECTION_REFUSED` | API belum menyala atau masih pelatihan awal. Cek `docker compose ps` dan `curl.exe -s http://localhost:8010/health/ready`. |
| 403 "Origin permintaan tidak diizinkan" saat Execute | `CORS_ORIGINS` di `.env` belum memuat alamat Swagger. Isi `CORS_ORIGINS=http://localhost:8010,http://127.0.0.1:8010`, lalu `docker compose up -d`. |
| 401 "Silakan login terlebih dahulu" | `LOGIN_REQUIRED=true` di `.env`. Ubah ke `false` lalu `docker compose up -d`, atau jalankan *Daftar akun*/*Masuk* di kelompok **Login**. |
| Halaman http://localhost:8010/docs kosong | Swagger UI mengambil tampilan dari internet (cdn.jsdelivr.net). Sambungkan laptop ke internet. |
| Port masih bentrok setelah ganti `.env` | Hentikan dulu: `docker compose down`, lalu `docker compose up -d`. |

Laptop yang menjalankan SatisView, CampusFlow, dan FoodSave bersamaan butuh RAM besar (dua
kluster HDFS + Airflow). Hentikan project yang tidak dipakai dengan `docker compose stop`.

## Menjalankan tanpa Docker (pengembangan)

Butuh Python 3.12 dan PostgreSQL. HDFS diganti folder lokal dengan struktur path yang sama.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements-dev.txt && pip install -e shared
export DATABASE_URL=postgresql+psycopg://foodsave:PASSWORD@localhost:5434/foodsave
export FOODSAVE_STORAGE=local LOCAL_STORAGE_ROOT=./storage/hdfs
export MLFLOW_TRACKING_URI=sqlite:///mlflow.db

(cd backend && alembic upgrade head)
PYTHONPATH=ml python -m foodsave_ml.bootstrap --seed dataset/raw/train.csv
PYTHONPATH=ml python -m foodsave_ml.pipeline
(cd backend && uvicorn app.main:app --reload)
```

## Pengujian

```bash
python backend/run_tests.py        # 58 tes: integrasi, keandalan, HDFS, email, Swagger, mode tanpa login (PostgreSQL *_test)
python -m pytest ml/tests          # 5 tes pipeline tanpa database
```

Tes backend menjalankan pipeline MLflow sungguhan (mode cepat), lalu menguji setiap halaman
API memakai model hasil pipeline tersebut, termasuk siklus data aktual → HDFS → pelatihan
ulang → versi model baru dipakai API. Tes keandalan memeriksa: semua endpoint privat menolak
akses tanpa login, ±1.000 input liar tidak pernah menghasilkan error 500, database mati → 503
lalu pulih sendiri, HDFS mati → model di memori tetap melayani, dan file model yang diubah
ditolak lewat checksum.

## Dataset

[Messy Food Waste Prediction Dataset (Kaggle)](https://www.kaggle.com/competitions/messy-food-waste-prediction-dataset/overview).
Hanya `train.csv` (911 baris berlabel) yang dipakai. `test.csv` dari Kaggle berisi baris yang
sama tanpa kolom target dan `submission.csv` berisi target yang sama, sehingga keduanya tidak
dipakai sebagai data uji. Data uji diambil dari 20% tanggal terakhir `train.csv`.
