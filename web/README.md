# FoodSave Web

Frontend Next.js untuk dashboard FoodSave Restaurant. UI dapat dijalankan mandiri dengan data demo, lalu memakai backend FastAPI ketika `NEXT_PUBLIC_API_URL` diatur.

## Menjalankan

```bash
pnpm install
pnpm dev
```

Contoh konfigurasi lokal:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Saat URL backend tersedia, frontend memakai login/register, prediksi dashboard, dan komposisi limbah dari endpoint FastAPI. Tanpa URL backend, tombol `Buka demo frontend` menjaga preview tetap dapat digunakan.

## Kontrak yang sudah dipakai

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/register`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout`
- `GET /api/v1/dashboard?on=YYYY-MM-DD`
- `GET /api/v1/insights/operational?starts_on=YYYY-MM-DD&ends_on=YYYY-MM-DD`
