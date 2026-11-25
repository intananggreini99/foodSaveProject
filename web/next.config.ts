import type { NextConfig } from 'next'

// Browser selalu memanggil /api/v1/... di alamat frontend (satu origin, cookie sesi ikut).
// Server Next.js meneruskannya ke FastAPI. Nilai dibaca saat build:
//   pnpm dev / pnpm build di laptop : http://localhost:8010 (port API FoodSave)
//   Docker Compose                  : http://api:8000 (diatur di web/Dockerfile)
const apiTarget = (process.env.API_PROXY_TARGET ?? 'http://localhost:8010').replace(/\/$/, '')

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // Docker memakai server mandiri (web/Dockerfile); pnpm dev/start di laptop tidak perlu.
  output: process.env.NEXT_OUTPUT === 'standalone' ? 'standalone' : undefined,
  poweredByHeader: false,
  experimental: {
    // Prediksi 7 hari dan pembuatan laporan bisa memakan beberapa detik.
    proxyTimeout: 120_000,
  },
  async rewrites() {
    return [
      { source: '/api/v1/:path*', destination: `${apiTarget}/api/v1/:path*` },
      { source: '/health/:path*', destination: `${apiTarget}/health/:path*` },
    ]
  },
}

export default nextConfig
