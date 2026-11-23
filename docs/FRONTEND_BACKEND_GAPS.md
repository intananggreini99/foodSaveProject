# Catatan Migrasi Frontend–Backend

## Sudah terhubung

- Login, register, cek sesi, logout: `/api/v1/auth/*`.
- Nama restoran: `/api/v1/restaurant`.
- Prediksi ringkas dashboard: `/api/v1/dashboard?on=YYYY-MM-DD`.
- Proporsi limbah per kategori: `/api/v1/insights/operational`.

## Masih perlu dikerjakan

- Backend belum berjalan di lingkungan ini: `http://localhost:8000/health/live` tidak merespons saat validasi.
- Halaman Input Data Harian masih memakai data contoh; hubungkan ke `daily-operations`, `predictions/preview`, dan endpoint prediksi tersimpan.
- Halaman Prediksi 7 Hari masih memakai data contoh; hubungkan ke `weekly-predictions`.
- Halaman Simulasi Porsi masih memakai perhitungan lokal; hubungkan ke `portion-scenarios`.
- Halaman Laporan masih memakai data contoh; hubungkan ke `reports/summary` dan `report-exports`.
- Halaman notifikasi dan pengaturan masih berupa UI; hubungkan ke `notifications`, `settings`, dan `users` bila diperlukan.
- Isi `CORS_ORIGINS` dengan origin frontend deployment dan aktifkan cookie aman saat production.
- Sediakan data operasional aktual untuk tanggal yang diminta dashboard agar kartu prediksi tidak kosong.

Tidak ada perubahan pada source backend dalam tahap frontend ini.
