# Pemeriksaan model FoodSave pada backend

Tujuannya memastikan API tidak sekadar mengeluarkan angka, tetapi memakai model,
preprocessing, dan urutan fitur yang sama dengan eksperimen yang sudah diuji.

## 1. Model yang dipakai untuk melayani prediksi

Model aktif adalah **Random Forest dengan preprocessing Robust**. Pemilihannya
memakai MAE validasi terkecil dari delapan eksperimen, bukan MAE test terkecil.

| Ukuran | Hasil model terpilih |
|---|---:|
| MAE validasi | 9,2478 kg |
| MAE test | 8,8671 kg |
| RMSE test | 11,0356 kg |
| R² test | 0,8208 |
| Observasi test | 174 |
| Jumlah fitur setelah preprocessing | 14 |

CatBoost Robust memiliki MAE test lebih rendah, tetapi keputusan tidak diganti
berdasarkan test. R² bukan akurasi klasifikasi. Angka di atas berlaku pada satu
split kronologis dan rancangan tuning yang tercatat dalam eksperimen.

Database menyimpan metadata delapan eksperimen pada `model_versions`, tetapi
runtime prediksi ini memakai Random Forest aktif. Model LSTM/XGBoost/CatBoost
yang tidak aktif tidak dimuat hanya untuk menampilkan metriknya.

## 2. Jalankan pemeriksaan otomatis

```powershell
.\.venv\Scripts\python.exe -m api.check_model --database
```

Perintah tersebut memeriksa:

1. File model dan preprocessing tersedia di folder models.
2. Nama model/bundle sesuai.
3. Jumlah dan urutan fitur identik dengan fitur yang diharapkan model.
4. Versi NumPy, pandas, scikit-learn, dan joblib cocok dengan lingkungan training
   jika metadata lingkungan eksperimen tersedia.
5. Pemetaan body input API menghasilkan prediksi yang sama dengan pipeline asli,
   sampai toleransi pembulatan empat desimal.
6. Mengubah target/kategori limbah yang tidak dipakai tidak mengubah fitur.
7. Prediksi pada 174 observasi test identik dengan CSV referensi.
8. MAE, RMSE, dan R² yang dihitung ulang cocok dengan manifest.
9. Pemenang di CSV eksperimen sesuai aturan validasi.
10. Checksum model dan preprocessing di PostgreSQL sama dengan file yang dipakai.

Hasil normal adalah `status: passed`. Laporan lokal berada di
`results/backend/backend-model-check.json` dan tidak ikut Git.

Untuk container:

```powershell
docker-compose exec api python -m api.check_model --database
```

Dataset mentah tidak dibundel ke image Docker. Karena itu `holdout_recheck` dapat
berstatus `not_available` di container. Pemeriksaan penuh 174 baris dilakukan
melalui perintah lokal dengan `dataset/raw/train.csv` dan CSV referensi tersedia.
Ini tidak boleh diartikan bahwa 174 observasi sudah diperiksa di container.

## 3. Pemetaan kolom

| Input API | Kolom yang diterima pipeline |
|---|---|
| `operation_date` | `date` |
| `meals_prepared` | `meals_served` |
| `kitchen_staff` | `kitchen_staff` |
| `temperature_c` | `temperature_C` |
| `humidity_percent` | `humidity_percent` |
| `special_event` | Angka 0/1 |
| `staff_experience` | Kategori pengalaman staf |

Pipeline kemudian menghitung kalender, rasio staf/porsi, interaksi acara-porsi,
normalisasi kategori, imputasi, dan batas outlier yang dipelajari dari training.
Kode API tidak memasang ulang median atau scaler dari input pengguna.

`actual_waste_kg`, `previous_waste_kg`, `waste_category`, jenis acara, dan catatan
tetap disimpan untuk kebutuhan aplikasi, tetapi tidak digunakan oleh model aktif
ini. Mengubah aktual yang ditimbang tidak boleh diam-diam memperbaiki prediksi.
Hal tersebut juga diuji pada tes integrasi backend.

## 4. Lokasi artefak dan catatan versi

Manifest: `models/best_model/selected_model.json`.

File model aktif: `models/best_model/RandomForest_robust.joblib`.

Preprocessing: `models/best_model/RandomForest_robust_preprocessing.joblib`.

Versi library inferensi dipasang melalui `requirements-api.txt`. Model dan
preprocessing disimpan sebagai pasangan; mengganti hanya salah satunya dapat
membuat urutan fitur atau hasil prediksi salah.

`model_versions` menyimpan checksum keduanya. `prediction_results` menyimpan
`model_version_id`, input snapshot, pengaturan snapshot, dan version operasi.
Input yang diedit tidak menulis ulang prediksi terdahulu.

Jika hasil training/model berubah, jalankan ulang evaluasi notebook/terminal,
perbarui manifest, kemudian:

```powershell
docker-compose exec api python -m api.seed_model
docker-compose exec api python -m api.check_model --database
```

File model berasal dari proses training yang tepercaya. Endpoint upload pengguna
tidak menerima atau mengeksekusi pickle/joblib/model.

## 5. Batas interpretasi

- Prediksi berbentuk kilogram; biaya rupiah bergantung harga bahan yang diisi.
- Interval dari residual validasi bersifat empiris, bukan jaminan cakupan.
- Threshold Aman/Waspada/Tinggi adalah pengaturan restoran yang dapat berubah.
- Prediksi tujuh hari membutuhkan input rencana untuk masing-masing hari.
- Simulasi menghitung ulang fitur rasio/interaksi dari porsi/staf baru.
- Penghematan dapat negatif; hasil simulasi tidak membuktikan hubungan kausal.
- Risiko kehabisan makanan tetap `unknown` sampai data permintaan tersedia.
- Porsi rekomendasi/penghematan yang belum dihitung tidak diisi dengan angka
  buatan. Kolom nullable disediakan untuk pengembangan rekomendasi berikutnya.

Rujukan: [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html)
dan [scikit-learn model persistence](https://scikit-learn.org/stable/model_persistence.html).
