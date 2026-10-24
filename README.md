# FoodSave Restaurant

Sistem prediksi sampah makanan restoran dan rekomendasi pengurangan jumlah porsi berbasis Machine Learning, dengan dashboard web untuk manajer restoran.

## Deskripsi

FoodSave Restaurant memperkirakan jumlah food waste harian (kg) dari data operasional restoran. Hasil ditampilkan bersama rentang estimasi, tingkat risiko (Aman / Waspada / Tinggi), dan simulasi what-if pengurangan porsi sebelum makanan dipersiapkan.

Proyek membandingkan 4 model dengan 2 pendekatan preprocessing (8 eksperimen):

| Model | Jenis |
|---|---|
| LSTM | Deep Learning |
| Random Forest Regressor | Ensemble Learning |
| XGBoost Regressor | Gradient Boosting |
| CatBoost Regressor | Gradient Boosting |

Preprocessing: **Standard** dan **Robust**.

## Arsitektur

```
Dataset Kaggle -> EDA -> Preprocessing -> Training 8 eksperimen -> Model terbaik
                                                                      |
                              Next.js (web) <-> FastAPI (api) <-> models/best_model
```

## Dataset

[Messy Food Waste Prediction Dataset (Kaggle)](https://www.kaggle.com/competitions/messy-food-waste-prediction-dataset/overview)

| Kolom | Keterangan |
|---|---|
| date | Tanggal pengukuran |
| meals_served | Jumlah porsi (string, format tidak konsisten) |
| kitchen_staff | Jumlah staf dapur (string, format tidak konsisten) |
| temperature_C | Suhu (C), ada nilai ekstrem |
| humidity_percent | Kelembapan (%) |
| day_of_week | Hari (0 = Senin, 6 = Minggu) |
| special_event | Acara khusus (1 = Ya, 0 = Tidak) |
| past_waste_kg | Food waste periode sebelumnya |
| staff_experience | Pengalaman staf (casing tidak konsisten) |
| waste_category | Kategori limbah (casing tidak konsisten) |
| food_waste_kg | **Target** prediksi (kg) |

Letakkan dataset hasil unduhan di `dataset/raw/`.

## Struktur Folder

```
FoodSave/
├── dataset/        # raw/ dan processed/
├── notebooks/      # 01 sampai 09: eksperimen dan evaluasi
├── src/            # logika ML (preprocessing, fitur, prediksi, risiko, what-if)
├── models/         # best_model/ dan scalers/
├── results/        # experiment_results.csv, evaluation/, visualizations/
├── api/            # backend FastAPI
├── web/            # frontend Next.js (App Router, Tailwind)
├── requirements.txt
└── README.md
```

## Halaman Dashboard

| Menu | Rute | Fungsi |
|---|---|---|
| Dashboard | `/` | Prediksi hari ini, status risiko, aktual vs prediksi, insight |
| Input Data Harian | `/input` | Input manual atau unggah CSV, pratinjau prediksi |
| Prediksi 7 Hari | `/prediksi` | Prediksi dan risiko 7 hari ke depan |
| Simulasi Porsi | `/simulasi` | What-if pengurangan porsi dan perubahan jumlah staf |
| Insight & Penyebab | `/insight` | Faktor penyebab limbah, beban staf, kategori |
| Laporan | `/laporan` | Ringkasan, temuan, rekomendasi, unduh PDF/Excel |

## Endpoint API

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/predict` | Prediksi food waste, rentang, status risiko |
| POST | `/what-if` | Simulasi perubahan porsi dan staf |
| GET | `/history` | Riwayat dan perbandingan aktual vs prediksi |
| GET | `/report` | Ringkasan laporan periode tertentu |

Dokumentasi interaktif: `http://localhost:8000/docs`

## Cara Menjalankan

Prasyarat: Python 3.10+, Node.js 18.18+, Git.

**1. Setup Python**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**2. Jalankan notebook** (berurutan 01 sampai 09)
```bash
jupyter notebook
```

**3. Jalankan backend**
```bash
uvicorn api.main:app --reload --port 8000
```

**4. Jalankan frontend** (terminal lain)
```bash
cd web
npm install
npm run dev
```
Buka http://localhost:3000

File `web/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Evaluasi

Metrik: MAE (utama), RMSE, R2, waktu training, waktu prediksi. Hasil di `results/experiment_results.csv`.

> Hasil eksperimen diisi setelah training dan evaluasi selesai.

## Catatan Validitas

- Pembagian data kronologis (train, validation, test), bukan random split.
- Imputasi, encoding, scaling, dan penanganan outlier hanya dipelajari dari data training.
- `waste_category` dan `past_waste_kg` dicek agar tidak menyebabkan data leakage.
- Hasil what-if adalah estimasi model, bukan bukti sebab-akibat.
- Batas risiko Aman / Waspada / Tinggi ditentukan dari distribusi data.

## Tools

Python, Pandas, NumPy, Scikit-learn, TensorFlow/Keras, XGBoost, CatBoost, FastAPI, Next.js, React, Tailwind CSS, Recharts, Jupyter/Google Colab.

## Lisensi

Proyek untuk keperluan akademik, Semester 5.