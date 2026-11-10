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
├── notebooks/      # 01 sampai 07: data dan pemodelan
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

**2. Jalankan notebook** (berurutan 01 sampai 07)
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

## Tambahan notebook lengkap tanpa menghapus kode tim

Seluruh sel kode asli notebook 03, 05, dan 07 tetap dipertahankan. Bagian baru
berjudul **Tambahan eksperimen lengkap** berada di bawah sel lama. Jalankan mulai
dari sel setup bagian tambahan tersebut sampai akhir. Bagian ini menyediakan
alur seragam agar delapan eksperimen dapat dibandingkan dengan adil. Keluaran
lama tidak dicampur karena pembagian data dan asumsi fiturnya berbeda. Script
otomatis melewati sel referensi lama bertag `foodsave-legacy`.

Notebook kosong 01, 02, 04, dan 06 dilengkapi langsung di lokasi yang sama.
Tidak ada folder notebook baru. Urutan alur tambahan adalah **01 sampai 07**.
Notebook 08 sengaja dihapus. Untuk memperbarui perbandingan delapan eksperimen,
jalankan `python -m src.experiment --model evaluate` setelah notebook model selesai.
Penjelasan ditulis dalam bahasa Indonesia, termasuk tujuan kode, metrik, kurva
pelatihan, kesalahan terbesar, importance, dan kesimpulan berdasarkan angka aktual.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m ipykernel install --prefix .venv --name foodsave --display-name "Python (FoodSave)"
python src/execute_notebooks.py
python src/validate_results.py
```

Di VS Code pilih interpreter `.venv\Scripts\python.exe`. Dataset `train.csv`
dan `test.csv` dari ZIP diletakkan di `dataset/raw/`; `submission.csv` tidak
dipakai sebagai sumber label tambahan. Dataset mentah tetap diabaikan Git.

Untuk eksperimen terminal tanpa menyimpan output notebook:

```powershell
python -m src.experiment --model all
python src/validate_results.py
```

Hasil tambahan berada di folder yang sudah ada:

- `results/evaluation/experiment_results.csv`: seluruh metrik delapan eksperimen.
- `results/evaluation/*_predictions.csv`: tanggal, aktual, prediksi, dan residual.
- `results/evaluation/*_curve.csv`: error setiap epoch/tahap/jumlah pohon.
- `results/evaluation/*_tuning.csv`: dua konfigurasi dan skor validasinya.
- `results/evaluation/data_audit.json` dan `split_manifest.csv`: audit dan split.
- `models/best_model/`: artefak baru dengan nama model/preprocessing tersendiri.
- `models/best_model/selected_model.json`: lokasi relatif model terpilih.
- `dataset/processed/validated_*.csv`: keluaran preprocessing tambahan.
- `results/FoodSave_Laporan_Perbandingan_Model.docx`: laporan lokal.

Model lama milik tim tidak ditimpa. Model baru belum otomatis dihubungkan ke API.
LSTM memerlukan konteks tujuh observasi fitur, bukan satu baris saja. Laporan
dibuat oleh `src/make_report.py` dengan `python-docx` dari file hasil eksperimen.
Jalankan kembali evaluasi dan laporan jika eksperimen berubah.

### Metode evaluasi alur tambahan

Tanggal dibagi sekitar 60/20/20 menjadi training, validasi, dan test; tanggal
yang sama tidak dipisahkan. Duplikat persis tanpa ID dibuang untuk kedua
preprocessing sebelum split. Median, modus, encoding, batas IQR, dan scaling
dipelajari dari training saja. Semua model memakai baris evaluasi yang sama
setelah enam observasi awal menjadi konteks LSTM. Target tidak di-clipping.

Model dipilih dari MAE validasi, dengan RMSE dan latensi validasi sebagai
pemecah seri. Test hanya untuk evaluasi akhir. Dua konfigurasi dicoba per
eksperimen, seed 42, tanpa melatih ulang pada validasi. Metrik meliputi MAE,
RMSE, R², MedAE, bias, WAPE, waktu training, total tuning, dan waktu prediksi.

Fitur operasional target diasumsikan tersedia saat perencanaan. `waste_category`,
`past_waste_kg`, dan ID tidak digunakan karena asal/waktu ketersediaannya belum
terverifikasi. Hari dihitung ulang dari tanggal. LSTM menggunakan tujuh
observasi, bukan tujuh hari; tidak ada ID restoran yang menjamin satu seri.
Adam pada LSTM menggunakan gradient descent; XGBoost dan CatBoost menggunakan
gradient boosting; Random Forest tidak menggunakan gradient descent.

Interval dari error validasi bersifat empiris/eksploratif karena validasi juga
digunakan untuk seleksi. Coverage test dilaporkan apa adanya, bukan dijamin 90%.
Batas risiko kuantil training belum menjadi batas operasional restoran. Hasil
satu split/seed tidak membuktikan keunggulan universal atau hubungan sebab-akibat.

`src/build_notebooks.py` adalah pembuat bagian tambahan. Script ini mempertahankan
sel lama dan mengganti hanya sel tambahan bertanda `foodsave_added`, sehingga
output tambahan akan kosong kembali. Jangan jalankan untuk sekadar membaca hasil.

Laporan Word/PDF dan gambar hasil eksperimen disimpan lokal dan diabaikan Git.
Output gambar yang tertanam di notebook dibersihkan untuk menjaga diff tetap ringan.
Kode visualisasi tetap tersedia sehingga gambar dapat dibuat ulang saat dijalankan.
