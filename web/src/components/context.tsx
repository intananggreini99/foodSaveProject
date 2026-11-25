'use client'

import { createContext, useContext } from 'react'
import type { Role, Settings } from '@/lib/api'

export type AppUser = {
  id: string
  email: string
  name: string
  role: Role
  restaurantName: string
}

export const PAGES = ['Overview', 'Input Data Harian', 'Prediksi 7 Hari', 'Simulasi Porsi', 'Insight & Penyebab', 'Laporan'] as const
export type Page = (typeof PAGES)[number]

export type AppContextValue = {
  user: AppUser
  settings: Settings | null
  setSettings: (settings: Settings) => void
  /** Tanggal hari ini (YYYY-MM-DD, zona waktu perangkat). */
  today: string
  /** Naik setiap ada perubahan data agar halaman memuat ulang. */
  version: number
  refresh: () => void
  navigate: (page: Page, focusDate?: string) => void
  /** Tanggal yang dibawa dari halaman lain (mis. Simulasi Porsi -> Input Data Harian). */
  focusDate: string | null
  clearFocus: () => void
  openDetail: (title: string, body: string) => void
  fail: (title: string, error: unknown) => void
  /** Pemilik dan manager boleh menyimpan; staf hanya membaca. */
  canEdit: boolean
}

export const AppContext = createContext<AppContextValue | null>(null)

export function useApp() {
  const value = useContext(AppContext)
  if (!value) throw new Error('useApp dipakai di luar AppContext')
  return value
}

export const errorText = (error: unknown) => (error instanceof Error ? error.message : 'Terjadi kesalahan yang tidak diketahui.')
