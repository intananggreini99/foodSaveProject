# Arsip riset (tidak dipakai runtime)

Folder ini menyimpan riset awal FoodSave sebelum backend dibangun ulang:

- `notebooks/` 01–07: pemahaman data, EDA, preprocessing Standard vs Robust, LSTM,
  Random Forest, XGBoost, CatBoost.
- `src/`: skrip eksperimen lama (`experiment.py`) dan pembuat laporan.
- `results/`: hasil eksperimen dan perbandingan model.
- `dataset/processed/`: hasil preprocessing lama.

Model hasil riset lama (`models/best_model/*.joblib`, ±38 MB) tidak disertakan lagi.
Model produksi sekarang dibuat oleh pipeline MLflow di `ml/` dan disimpan di HDFS.

Untuk menjalankan ulang notebook, salin `dataset/raw/train.csv` ke `research/dataset/raw/`
lalu pasang `requirements.txt` di folder ini.
