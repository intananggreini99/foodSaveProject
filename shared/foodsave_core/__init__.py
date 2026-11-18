"""Kode bersama FoodSave.

Dipakai oleh dua sisi sistem agar file .pkl selalu bisa dibuka kembali:
- pipeline MLflow (ml/) yang melatih dan menyimpan model ke HDFS;
- FastAPI (backend/) yang memuat model versi aktif dari HDFS ke memori.

Kelas FoodPreprocessor harus berasal dari modul yang sama di kedua sisi,
karena pickle menyimpan nama modul kelasnya (foodsave_core.preprocessing).
"""

__version__ = "2.0.0"
