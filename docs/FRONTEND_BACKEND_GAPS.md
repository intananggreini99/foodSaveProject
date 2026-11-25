# Integrasi Frontend-Backend

Frontend Next.js (`web/`) sudah terhubung penuh ke FastAPI. Data demo, angka contoh, dan
dataset cadangan di frontend sudah dihapus; setiap halaman memakai data restoran yang login.
Kode backend tidak diubah untuk integrasi ini.

## Integrasi aktif

- [x] Daftar, masuk, cek sesi, keluar (`/auth/*`); kembali ke layar Masuk saat sesi berakhir.
- [x] Nama restoran (`/restaurant`) dan pengaturan restoran (`GET/PUT /settings`) di panel akun.
- [x] Overview: `dashboard`, `dashboard/trend`, `reports/summary`, `insights/operational`,
      `portion-scenarios/options`; tombol *Jalankan prediksi* dan *Terapkan Saran*.
- [x] Input Data Harian: `predictions/preview` (pratinjau langsung), `POST/PUT daily-operations`,
      `daily-operations/{id}/predict`, riwayat `daily-operations/{id}/corrections`.
- [x] Unggah CSV/Excel: `imports?apply=false` (periksa) lalu `imports?apply=true` (simpan), dan
      prediksi opsional untuk setiap tanggal yang tersimpan.
- [x] Prediksi 7 Hari: `weekly-predictions` (buat, baca, ubah satu hari).
- [x] Simulasi Porsi: `portion-scenarios/options`, `portion-scenarios`, `portion-scenarios/{id}/apply`;
      jumlah porsi bebas di luar 4 skenario diterapkan lewat `PUT daily-operations` + prediksi.
- [x] Insight & Penyebab: `daily-operations` (90 hari) dan `insights/operational`.
- [x] Laporan: `reports/summary`, `report-exports` (PDF/XLSX dibuat backend, diunduh lewat
      `report-exports/{id}/file`), email lewat pekerja laporan dan Mailpit.
- [x] Notifikasi: `notifications` dan `notifications/{id}/read`.
- [x] Status backend dan model aktif: `/health/ready`.

## Perubahan tampilan yang perlu diketahui

- Tombol *Buka demo frontend* dihapus; aplikasi selalu memakai backend.
- Tombol *Hapus* di tabel 5 Input Terakhir diganti *Riwayat*, karena backend sengaja tidak
  menghapus input harian (koreksi dicatat sebagai riwayat).
- Form Input Data Harian mendapat kolom *Limbah aktual*, *Jenis acara* (saat acara khusus
  dicentang), dan *Alasan perubahan* (saat mengubah tanggal yang sudah ada), karena kolom ini
  dibutuhkan API.
- Batas warna Aman/Waspada/Tinggi mengikuti Pengaturan restoran, bukan angka tetap 10/15 kg.
- Simulasi Porsi punya pilihan *Rencana dasar* karena simulasi backend selalu berangkat dari
  satu input harian yang tersimpan.
- Prediksi 7 Hari punya tombol *Buat Rencana Baru*; isian awal ketujuh hari diambil dari input
  harian terakhir lalu bisa diubah per hari.

## Batasan yang tersisa

- *Risiko kehabisan* di Simulasi Porsi adalah aturan frontend (pengurangan di atas 15% = tinggi),
  bukan keluaran model.
- *Potensi hemat* di Prediksi 7 Hari dihitung frontend: biaya limbah di atas batas Aman.
- Harga bahan per kg akun baru bernilai 0 (bawaan backend); frontend menampilkan pengingat
  sampai harga diisi di Pengaturan.
