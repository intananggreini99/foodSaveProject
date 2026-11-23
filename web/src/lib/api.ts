const baseUrl = (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/$/, '')

export const hasApiUrl = Boolean(baseUrl)

type ApiUser = {
  id: string
  name: string
  email: string
  role: string
  restaurant_id: string
}

type ApiRestaurant = { name?: string }

export type WasteComposition = {
  label: string
  value: number
  color: string
}

export type DashboardData = {
  prediction?: {
    predicted_waste_kg?: number | string
    interval_lower_kg?: number | string
    interval_upper_kg?: number | string
  } | null
}

export type DailyWastePoint = {
  date: string
  wasteKg: number
  inputTime?: string
}

export type TrendPoint = {
  date: string
  actual_waste_kg?: number | string | null
  predicted_waste_kg?: number | string | null
}

const colors = ['#2d826b', '#74a58e', '#a9c77b', '#e8ad65', '#c77d5d']

function categoryLabel(value: string | null | undefined) {
  const normalized = (value ?? '').toLowerCase()
  if (normalized.includes('meat') || normalized.includes('daging')) return 'Daging'
  if (normalized.includes('vegetable') || normalized.includes('sayur')) return 'Sayur'
  if (normalized.includes('dairy') || normalized.includes('susu')) return 'Susu'
  if (normalized.includes('grain') || normalized.includes('biji')) return 'Biji-bijian'
  return value || 'Lainnya'
}

async function request<T>(path: string, init?: RequestInit) {
  if (!hasApiUrl) throw new Error('Backend belum dikonfigurasi')
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!response.ok) throw new Error((await response.text()) || `HTTP ${response.status}`)
  return response.status === 204 ? undefined as T : response.json() as Promise<T>
}

export async function login(email: string, password: string) {
  return request<ApiUser>('/api/v1/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export async function getMe() {
  return request<ApiUser>('/api/v1/auth/me')
}

export async function getRestaurant() {
  return request<ApiRestaurant>('/api/v1/restaurant')
}

export async function logout() {
  return request<void>('/api/v1/auth/logout', { method: 'POST' })
}

export async function register(payload: { name: string; restaurantName: string; email: string; password: string }) {
  return request<ApiUser>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({
      name: payload.name,
      restaurant_name: payload.restaurantName,
      email: payload.email,
      password: payload.password,
    }),
  })
}

export async function getOperationalInsights(): Promise<WasteComposition[]> {
  if (!hasApiUrl) return []
  const today = new Date().toISOString().slice(0, 10)
  const response = await request<{ categories?: Array<{ category?: string; actual_waste_kg?: number | null }> }>(
    `/api/v1/insights/operational?starts_on=2022-01-01&ends_on=${today}`,
  )
  const categories = (response.categories ?? []).filter((item) => Number(item.actual_waste_kg) > 0)
  const total = categories.reduce((sum, item) => sum + Number(item.actual_waste_kg), 0)
  if (!total) return []
  return categories.map((item, index) => ({
    label: categoryLabel(item.category),
    value: Math.round((Number(item.actual_waste_kg) / total) * 100),
    color: colors[index % colors.length],
  }))
}

export async function getDashboard(): Promise<DashboardData> {
  const today = new Date().toISOString().slice(0, 10)
  return request<DashboardData>(`/api/v1/dashboard?on=${today}`)
}

export async function getDailyOperations(): Promise<DailyWastePoint[]> {
  if (!hasApiUrl) return []
  const end = new Date()
  const start = new Date(end)
  start.setDate(end.getDate() - 27)
  const format = (date: Date) => date.toISOString().slice(0, 10)
  const response = await request<{ items?: Array<{ operation_date?: string; actual_waste_kg?: number | string | null; created_at?: string }> }>(
    `/api/v1/daily-operations?starts_on=${format(start)}&ends_on=${format(end)}&limit=28`,
  )
  return (response.items ?? [])
    .filter((item) => item.operation_date && Number(item.actual_waste_kg) > 0)
    .map((item) => ({ date: item.operation_date as string, wasteKg: Number(item.actual_waste_kg), inputTime: item.created_at }))
    .sort((left, right) => left.date.localeCompare(right.date))
}

export async function getTrend(): Promise<{ series?: TrendPoint[] }> {
  if (!hasApiUrl) return {}
  const end = new Date().toISOString().slice(0, 10)
  return request<{ series?: TrendPoint[] }>(`/api/v1/dashboard/trend?end=${end}&days=30`)
}

export function toAppUser(user: ApiUser, restaurantName = 'Restoran FoodSave') {
  return {
    id: String(user.id),
    email: user.email,
    name: user.name,
    restaurantName,
  }
}
