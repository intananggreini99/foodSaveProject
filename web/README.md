# FoodSave - frontend web (Next.js)

Rilis lokal di laptop (localhost), tidak untuk deploy.

Cara yang disarankan: jalankan lewat Docker dari folder proyek (layanan `web`):

```powershell
docker compose up -d --build        # semua layanan
docker compose up -d --build web    # hanya frontend
```

Buka http://localhost:3010 (port mengikuti `FOODSAVE_WEB_PORT` di `.env`).

Menjalankan langsung di Windows (`npm install` lalu `npm run dev`) hanya berhasil bila
Windows tidak memblokir biner native Next.js (Smart App Control/WDAC).

Halaman awal menampilkan status sistem (`/health/ready`) dan alamat layanan lokal.
Halaman lain masih kerangka dan belum terhubung ke API.
