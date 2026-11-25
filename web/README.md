# FoodSave Web

Frontend Next.js untuk FoodSave Restaurant. Semua data diambil dari backend FastAPI
(`/api/v1`); tidak ada data demo atau angka contoh di kode.

## Cara kerja koneksi ke backend

Browser hanya memanggil alamat frontend. Server Next.js meneruskan `/api/v1/*` dan
`/health/*` ke FastAPI (lihat `next.config.ts`), sehingga cookie sesi httpOnly dari backend
tetap satu origin dan tidak perlu CORS di browser.

| Cara menjalankan | Alamat frontend | Diteruskan ke |
|---|---|---|
| `docker compose up -d --build` (dari folder proyek) | http://localhost:3010 | `http://api:8000` di jaringan Docker |
| `pnpm dev` (di folder `web`) | http://localhost:3010 | `http://localhost:8010` (ubah dengan `API_PROXY_TARGET`) |

Backend menolak POST/PUT dari origin yang tidak terdaftar. `compose.yaml` otomatis
menambahkan `http://localhost:3010` ke `CORS_ORIGINS`; saat menjalankan API di luar Docker,
tambahkan alamat itu sendiri.

## Menjalankan tanpa Docker

```bash
pnpm install
pnpm dev          # http://localhost:3010
pnpm typecheck    # cek TypeScript
pnpm build        # build produksi (pnpm start untuk menjalankannya)
```

## Struktur

| File | Isi |
|---|---|
| `src/app/page.tsx` | Cek sesi (`GET /auth/me`), layar Masuk/Daftar, kembali ke Masuk saat sesi berakhir (401) |
| `src/app/AuthScreen.tsx` | Form masuk dan daftar akun pemilik |
| `src/app/FoodSaveApp.tsx` | Kerangka: sidebar, header, notifikasi, dialog, panel akun + pengaturan restoran |
| `src/components/Overview.tsx` | Dashboard harian |
| `src/components/InputHarian.tsx` | Input harian, pratinjau, koreksi, unggah CSV/Excel, contoh CSV 30 hari |
| `src/components/Prediksi7Hari.tsx` | Rencana tujuh hari |
| `src/components/SimulasiPorsi.tsx` | Simulasi porsi dan staf |
| `src/components/Insight.tsx` | Pola limbah dari data operasional |
| `src/components/Laporan.tsx` | Ringkasan periode, ekspor PDF/Excel, email |
| `src/lib/api.ts` | Klien semua endpoint FastAPI yang dipakai |
| `src/lib/format.ts` | Format tanggal/angka Indonesia, label, dan perhitungan pola |

Angka pola di halaman Insight, Laporan, dan Overview (hari paling boros, selisih limbah saat
acara khusus, dan sebagainya) adalah selisih rata-rata limbah aktual dari data restoran,
bukan sebab-akibat. Prediksi dan skenario selalu berasal dari model aktif di backend.
