# Checklist Migrasi Frontend-Backend

Dokumen ini mencatat batas integrasi saat frontend disiapkan. Source backend tidak diubah.

## Integrasi aktif

- [x] Login, register, cek sesi, dan logout melalui `/api/v1/auth/*`.
- [x] Nama restoran melalui `/api/v1/restaurant`.
- [x] Ringkasan dashboard melalui `/api/v1/dashboard?on=YYYY-MM-DD`.
- [x] Proporsi limbah melalui `/api/v1/insights/operational`.
- [x] Data kalender limbah memakai `/api/v1/daily-operations` bila API tersedia.
- [x] Tren limbah memakai `/api/v1/dashboard/trend` bila API tersedia.
- [x] Fallback frontend memakai agregasi dataset, bukan angka acak.

## Pekerjaan frontend yang masih menunggu API

- [ ] Form Input Data Harian mengirim data ke `daily-operations`.
- [ ] Tombol prediksi menyimpan hasil melalui endpoint prediksi yang disepakati.
- [ ] Prediksi tujuh hari mengambil data dari `weekly-predictions`.
- [ ] Simulasi porsi menyimpan skenario melalui `portion-scenarios`.
- [ ] Laporan mengambil ringkasan dari `reports/summary` dan `report-exports`.
- [ ] Notifikasi mengambil data dari `notifications`.
- [ ] Pengaturan akun mengambil dan menyimpan data melalui `settings` dan `users`.
- [ ] Kirim email laporan memakai layanan email backend; frontend saat ini hanya menampilkan pratinjau.

## Yang perlu disiapkan tim backend

- [ ] Jalankan dan verifikasi `http://localhost:8000/health/live`.
- [ ] Pastikan kontrak request/response dan autentikasi cookie untuk endpoint di atas sudah final.
- [ ] Tambahkan CORS origin deployment frontend.
- [ ] Aktifkan cookie aman, HTTPS, dan kebijakan credential saat production.
- [ ] Sediakan data operasional aktual untuk tanggal dashboard yang diminta.
- [ ] Sediakan timestamp `created_at` bila waktu input ingin ditampilkan di tooltip kalender.

## Catatan data

- Dataset fallback yang tersedia berisi catatan historis 2024-08-27 sampai 2024-09-26.
- Header dan forecast memakai tanggal perangkat saat ini; nilai forecast tidak dianggap sebagai data aktual.
- Jika API gagal atau kosong, frontend tetap berjalan dengan fallback yang ditandai untuk migrasi.
