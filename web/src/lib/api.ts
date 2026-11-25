// Klien FastAPI FoodSave (/api/v1). Browser memanggil alamat frontend sendiri; server
// Next.js meneruskan /api/v1/* ke backend (lihat next.config.ts), sehingga cookie sesi
// httpOnly dari backend ikut otomatis tanpa pengaturan CORS di browser.

const API = '/api/v1'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

let onUnauthorized: (() => void) | null = null

/** Dipanggil saat sesi berakhir (401) agar aplikasi kembali ke layar Masuk. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler
}

type Validation = { loc?: Array<string | number>; msg?: string }

function readDetail(status: number, body: unknown) {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return (detail as Validation[])
      .map((item) => {
        const field = (item.loc ?? []).filter((part) => part !== 'body' && part !== 'query').join('.')
        const message = (item.msg ?? '').replace(/^Value error, /, '')
        return field ? `${field}: ${message}` : message
      })
      .join(' · ')
  }
  if (status >= 500) return 'Backend FoodSave tidak dapat dihubungi atau sedang bermasalah. Coba lagi beberapa saat.'
  return `Permintaan gagal (HTTP ${status}).`
}

async function request<T>(path: string, init: RequestInit & { skipAuthRedirect?: boolean; retried?: boolean } = {}): Promise<T> {
  const { skipAuthRedirect, retried, ...options } = init
  const isForm = options.body instanceof FormData
  let response: Response
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      credentials: 'same-origin',
      headers: isForm ? options.headers : { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, 'Backend FoodSave tidak dapat dihubungi. Pastikan layanan API sudah berjalan.')
  }
  if (response.status === 204) return undefined as T
  const text = await response.text()
  let body: unknown = null
  try {
    body = text ? JSON.parse(text) : null
  } catch {
    body = null
  }
  // Proxy Next.js gagal tersambung ke API (balasan bukan JSON): ulangi sekali untuk permintaan baca.
  const method = (options.method ?? 'GET').toUpperCase()
  if (response.status >= 500 && body === null && method === 'GET' && !retried) {
    await new Promise((resolve) => setTimeout(resolve, 300))
    return request<T>(path, { ...init, retried: true } as typeof init)
  }
  if (!response.ok) {
    if (response.status === 401 && !skipAuthRedirect) onUnauthorized?.()
    throw new ApiError(response.status, readDetail(response.status, body))
  }
  return body as T
}

const json = (method: string, payload?: unknown): RequestInit => ({
  method,
  body: payload === undefined ? undefined : JSON.stringify(payload),
})

const query = (params: Record<string, string | number | boolean | null | undefined>) => {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  })
  const text = search.toString()
  return text ? `?${text}` : ''
}

// ---------- Tipe data dari backend ------------------------------------------------

export type Role = 'owner' | 'manager' | 'staff'
export type Experience = 'beginner' | 'intermediate' | 'expert'
export type RiskLevel = 'safe' | 'warning' | 'high'

export type ApiUser = {
  id: string
  name: string
  email: string
  role: Role
  restaurant_id: string
}

export type Restaurant = { id: string; name: string }

export type Settings = {
  ingredient_cost_per_kg: number
  safe_max_kg: number
  warning_max_kg: number
  max_portions: number
  reduction_target_percent: number
  high_risk_notifications: boolean
  report_recipient_email: string | null
}

export type DailyFields = {
  operation_date: string
  meals_prepared: number
  kitchen_staff: number
  staff_experience: Experience
  special_event: boolean
  event_type: string | null
  temperature_c: number
  humidity_percent: number
  previous_waste_kg: number | null
  waste_category: string | null
  actual_waste_kg: number | null
  manager_notes: string | null
}

export type DailyOperation = DailyFields & {
  id: string
  version: number
  source: string
  import_id: string | null
  created_at: string
  updated_at: string
}

export type Prediction = {
  id?: string
  predicted_waste_kg: number
  interval_lower_kg: number
  interval_upper_kg: number
  risk_level: RiskLevel
  portions_per_staff: number
  estimated_waste_cost: number
  outside_training_range: boolean
  outside_fields?: string[]
  operation_version?: number | null
  created_at?: string
}

export type Dashboard = {
  operation: DailyOperation | null
  prediction: Prediction | null
  prediction_is_stale: boolean
  applied_scenarios: Scenario[]
  unread_notifications: number
  thresholds: { safe_max_kg: number; warning_max_kg: number }
  reduction_target_percent: number
  model: { version_key: string; test_mae: number | null } | null
}

export type TrendPoint = {
  date: string
  actual_waste_kg: number | null
  predicted_waste_kg: number | null
  interval_lower_kg: number | null
  interval_upper_kg: number | null
  risk_level: RiskLevel | null
}

export type Trend = { starts_on: string; ends_on: string; series: TrendPoint[]; paired_days: number; mae_kg: number | null }

export type Insights = {
  staff_load: Array<{ group: string; operation_count: number; actual_recorded_count: number; average_actual_waste_kg: number | null }>
  categories: Array<{ category: string; operation_count: number; actual_waste_kg: number | null }>
}

export type ScenarioOption = {
  reduction_percent: number
  simulated_portions: number
  kitchen_staff: number
  predicted_waste_kg: number
  savings_kg: number
  savings_amount: number
  risk_level: RiskLevel
  outside_training_range: boolean
}

export type ScenarioOptions = {
  daily_operation_id: string
  operation_version: number
  baseline_portions: number
  baseline_waste_kg: number
  baseline_risk_level: RiskLevel
  model_version: string
  options: ScenarioOption[]
}

export type Scenario = {
  id: string
  daily_operation_id: string
  application_date: string
  baseline_portions: number
  simulated_portions: number
  kitchen_staff: number
  reduction_percent: number
  predicted_waste_kg: number
  baseline_waste_kg: number
  savings_kg: number
  savings_amount: number
  status: 'draft' | 'saved' | 'applied'
  created_at: string
}

export type PlanDay = {
  id: string
  prediction_date: string
  input_snapshot: DailyFields
  version: number
  prediction: Prediction | null
}

export type WeeklyPlan = { id: string; title: string; starts_on: string; created_at: string; days?: PlanDay[] }

export type ImportFinding = { row: number; status: 'invalid' | 'unusual'; messages: string[] }

export type DataImport = {
  id: string
  file_name: string
  status: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  unusual_rows: number
  applied_rows: number
  validation_results: ImportFinding[]
}

export type Correction = { id: string; reason: string; previous_values: Partial<DailyFields>; new_values: Partial<DailyFields>; created_at: string }

export type ReportSummary = {
  operation_count: number
  actual_recorded_count: number
  actual_missing_count: number
  total_actual_waste_kg: number | null
  average_actual_waste_kg: number | null
  total_portions: number
  estimated_actual_waste_cost: number | null
  prediction_pairs: number
  prediction_mae_kg: number | null
  by_category: Array<{ category: string | null; operation_count: number; actual_waste_kg: number | null }>
}

export type ReportExport = {
  id: string
  file_name: string | null
  file_format: 'pdf' | 'xlsx'
  generation_status: string
  email_status: string
  email_recipient: string | null
}

export type Notification = { id: string; title: string; message: string; read_at: string | null; created_at: string }

// ---------- Akun -------------------------------------------------------------------

export const login = (email: string, password: string) =>
  request<ApiUser>('/auth/login', { ...json('POST', { email, password }), skipAuthRedirect: true })

export const register = (payload: { name: string; restaurantName: string; email: string; password: string }) =>
  request<ApiUser>('/auth/register', {
    ...json('POST', { name: payload.name, restaurant_name: payload.restaurantName, email: payload.email, password: payload.password }),
    skipAuthRedirect: true,
  })

export const getMe = () => request<ApiUser>('/auth/me', { skipAuthRedirect: true })
export const logout = () => request<void>('/auth/logout', { method: 'POST', skipAuthRedirect: true })
export const getRestaurant = () => request<Restaurant>('/restaurant')
export const getSettings = () => request<Settings>('/settings')
export const updateSettings = (body: Settings) => request<Settings>('/settings', json('PUT', body))

// ---------- Input data harian & prediksi -------------------------------------------

export const listOperations = (params: { starts_on?: string; ends_on?: string; waste_category?: string | null; limit?: number; offset?: number } = {}) =>
  request<{ items: DailyOperation[]; total: number }>(`/daily-operations${query(params)}`)

/** Semua input dalam rentang tanggal (backend membatasi 200 baris per halaman). */
export async function allOperations(starts_on: string, ends_on: string, waste_category?: string | null) {
  const items: DailyOperation[] = []
  for (let offset = 0; offset < 2000; offset += 200) {
    const page = await listOperations({ starts_on, ends_on, waste_category, limit: 200, offset })
    items.push(...page.items)
    if (items.length >= page.total || page.items.length === 0) break
  }
  return items.sort((a, b) => a.operation_date.localeCompare(b.operation_date))
}

export const createOperation = (body: DailyFields) => request<DailyOperation>('/daily-operations', json('POST', body))
export const updateOperation = (id: string, body: DailyFields & { expected_version: number; correction_reason: string }) =>
  request<DailyOperation>(`/daily-operations/${id}`, json('PUT', body))
export const getCorrections = (id: string) => request<Correction[]>(`/daily-operations/${id}/corrections`)
export const predictOperation = (id: string) => request<Prediction>(`/daily-operations/${id}/predict`, { method: 'POST' })
export const previewPrediction = (body: Pick<DailyFields, 'operation_date' | 'meals_prepared' | 'kitchen_staff' | 'staff_experience' | 'special_event' | 'temperature_c' | 'humidity_percent'>) =>
  request<Prediction>('/predictions/preview', json('POST', body))

export function uploadImport(file: File, apply: boolean) {
  const form = new FormData()
  form.append('file', file)
  return request<DataImport>(`/imports${query({ apply })}`, { method: 'POST', body: form })
}

// ---------- Dashboard, insight, laporan --------------------------------------------

export const getDashboard = (on: string) => request<Dashboard>(`/dashboard${query({ on })}`)
export const getTrend = (end: string, days: number) => request<Trend>(`/dashboard/trend${query({ end, days })}`)
export const getInsights = (starts_on: string, ends_on: string) => request<Insights>(`/insights/operational${query({ starts_on, ends_on })}`)
export const getReportSummary = (starts_on: string, ends_on: string, waste_category?: string | null) =>
  request<ReportSummary>(`/reports/summary${query({ starts_on, ends_on, waste_category })}`)

export const createReport = (body: {
  starts_on: string
  ends_on: string
  period_type: 'weekly' | 'monthly' | 'custom'
  waste_category: string | null
  search: string | null
  sort_order: 'date_asc' | 'date_desc'
  file_format: 'pdf' | 'xlsx'
  email_recipient?: string | null
  email_subject?: string | null
  email_message?: string | null
}) => request<ReportExport>('/report-exports', json('POST', body))

export const reportFileUrl = (id: string) => `${API}/report-exports/${id}/file`

export const getNotifications = () => request<Notification[]>('/notifications?limit=30')
export const markNotificationRead = (id: string) => request<Notification>(`/notifications/${id}/read`, { method: 'PATCH' })

// ---------- Rencana 7 hari ----------------------------------------------------------

export const listPlans = () => request<WeeklyPlan[]>('/weekly-predictions?limit=20')
export const getPlan = (id: string) => request<WeeklyPlan>(`/weekly-predictions/${id}`)
export const createPlan = (body: { title: string; starts_on: string; days: DailyFields[] }) =>
  request<WeeklyPlan>('/weekly-predictions', json('POST', body))
export const updatePlanDay = (planId: string, dayId: string, body: DailyFields & { expected_version: number; correction_reason: string }) =>
  request<WeeklyPlan>(`/weekly-predictions/${planId}/days/${dayId}`, json('PUT', body))

// ---------- Simulasi porsi ----------------------------------------------------------

export const getScenarioOptions = (daily_operation_id: string, kitchen_staff: number | null) =>
  request<ScenarioOptions>('/portion-scenarios/options', json('POST', { daily_operation_id, kitchen_staff }))
export const listScenarios = (daily_operation_id?: string) =>
  request<Scenario[]>(`/portion-scenarios${query({ daily_operation_id, limit: 200 })}`)
export const createScenario = (body: {
  daily_operation_id: string
  reduction_percent: number
  kitchen_staff: number | null
  application_date: string
  notes: string | null
  status: 'draft' | 'saved'
}) => request<Scenario>('/portion-scenarios', json('POST', body))
export const applyScenario = (id: string, expected_operation_version: number) =>
  request<{ scenario: Scenario; operation: DailyOperation; prediction?: Prediction; already_applied: boolean }>(
    `/portion-scenarios/${id}/apply`,
    json('POST', { expected_operation_version }),
  )
