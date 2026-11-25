// Format tampilan dan perhitungan kecil di sisi frontend (tanpa angka contoh).
import type { DailyFields, DailyOperation, Experience, RiskLevel, Settings } from './api'

// ---------- Tanggal (zona waktu perangkat, bukan UTC) -------------------------------

export function isoDate(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

export const todayIso = () => isoDate(new Date())

export function parseDate(value: string) {
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  return new Date(year, month - 1, day)
}

export function addDays(value: string, days: number) {
  const date = parseDate(value)
  date.setDate(date.getDate() + days)
  return isoDate(date)
}

export function daysBetween(start: string, end: string) {
  return Math.round((parseDate(end).getTime() - parseDate(start).getTime()) / 86_400_000)
}

export const monthStart = (value: string) => `${value.slice(0, 7)}-01`

export function monthEnd(value: string) {
  const date = parseDate(monthStart(value))
  date.setMonth(date.getMonth() + 1, 0)
  return isoDate(date)
}

export const WEEKDAYS = ['Minggu', 'Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu']
export const weekday = (value: string) => WEEKDAYS[parseDate(value).getDay()]

const formatter = (options: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('id-ID', options)
export const shortDate = (value: string) => formatter({ day: 'numeric', month: 'short' }).format(parseDate(value))
export const mediumDate = (value: string) => formatter({ day: 'numeric', month: 'short', year: 'numeric' }).format(parseDate(value))
export const longDate = (value: string) => formatter({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }).format(parseDate(value))
export const monthName = (value: string) => formatter({ month: 'long', year: 'numeric' }).format(parseDate(value))
export const clockTime = (value?: string | null) => (value ? formatter({ hour: '2-digit', minute: '2-digit' }).format(new Date(value)) : '-')

export function rangeLabel(start: string, end: string) {
  if (start.slice(0, 7) === end.slice(0, 7)) return `${parseDate(start).getDate()}–${mediumDate(end)}`
  return `${shortDate(start)} – ${mediumDate(end)}`
}

// ---------- Angka ----------------------------------------------------------------

export const num = (value: number | string | null | undefined) => (value === null || value === undefined || value === '' ? null : Number(value))

export function kg(value: number | string | null | undefined, digits = 1) {
  const number = num(value)
  return number === null ? '-' : number.toLocaleString('id-ID', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

export function rupiah(value: number | string | null | undefined) {
  const number = num(value)
  return number === null ? '-' : `Rp${Math.round(number).toLocaleString('id-ID')}`
}

export function shortRupiah(value: number) {
  if (Math.abs(value) >= 1_000_000) return { value: `Rp${(value / 1_000_000).toLocaleString('id-ID', { maximumFractionDigits: 2 })}`, unit: 'juta' }
  if (Math.abs(value) >= 1_000) return { value: `Rp${(value / 1_000).toLocaleString('id-ID', { maximumFractionDigits: 1 })}`, unit: 'ribu' }
  return { value: `Rp${Math.round(value)}`, unit: '' }
}

export const percent = (value: number, digits = 0) => `${value.toLocaleString('id-ID', { maximumFractionDigits: digits })}%`

export const average = (values: number[]) => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : null)

// ---------- Label domain ----------------------------------------------------------

export type RiskLabel = 'Aman' | 'Waspada' | 'Tinggi'
export const riskLabel: Record<RiskLevel, RiskLabel> = { safe: 'Aman', warning: 'Waspada', high: 'Tinggi' }

/** Tingkat risiko untuk angka limbah apa pun memakai batas di Pengaturan restoran. */
export function riskOf(value: number | null | undefined, settings: Pick<Settings, 'safe_max_kg' | 'warning_max_kg'> | null): RiskLabel | null {
  if (value === null || value === undefined || !settings) return null
  if (value <= Number(settings.safe_max_kg)) return 'Aman'
  return value <= Number(settings.warning_max_kg) ? 'Waspada' : 'Tinggi'
}

export const experienceLabel: Record<Experience, string> = { beginner: 'Pemula', intermediate: 'Menengah', expert: 'Ahli' }

export const CATEGORIES: Array<[string, string]> = [
  ['meat', 'Daging'],
  ['vegetables', 'Sayur'],
  ['dairy', 'Susu'],
  ['grains', 'Biji-bijian'],
]

export function categoryLabel(value: string | null | undefined) {
  const normalized = (value ?? '').toLowerCase()
  if (!normalized || normalized === 'tanpa kategori') return 'Tanpa kategori'
  if (normalized.includes('meat') || normalized.includes('daging')) return 'Daging'
  if (normalized.includes('vegetable') || normalized.includes('sayur')) return 'Sayur'
  if (normalized.includes('dairy') || normalized.includes('susu')) return 'Susu'
  if (normalized.includes('grain') || normalized.includes('biji')) return 'Biji-bijian'
  return value as string
}

export const CATEGORY_COLORS = ['#2d826b', '#74a58e', '#a9c77b', '#e8ad65', '#c77d5d', '#94a3b8']

export const roleLabel: Record<string, string> = { owner: 'Pemilik Restoran', manager: 'Restaurant Manager', staff: 'Staf Dapur' }

// ---------- Pola dari data operasional (deskriptif, bukan sebab-akibat) ------------

export const actual = (row: DailyOperation) => num(row.actual_waste_kg)
export const withActual = (rows: DailyOperation[]) => rows.filter((row) => actual(row) !== null)

export function weekdayAverages(rows: DailyOperation[]) {
  const buckets = new Map<number, number[]>()
  withActual(rows).forEach((row) => {
    const day = parseDate(row.operation_date).getDay()
    buckets.set(day, [...(buckets.get(day) ?? []), actual(row) as number])
  })
  return [...buckets.entries()]
    .map(([day, values]) => ({ day: WEEKDAYS[day], average: average(values) as number, count: values.length }))
    .sort((a, b) => b.average - a.average)
}

export type Factor = { label: string; impact: number; detail: string }

/** Selisih rata-rata limbah aktual antara dua kelompok input. */
export function factorDifferences(rows: DailyOperation[]): Factor[] {
  const data = withActual(rows)
  const meals = data.map((row) => row.meals_prepared).sort((a, b) => a - b)
  const median = meals.length ? meals[Math.floor(meals.length / 2)] : 0
  const compare = (label: string, inGroup: (row: DailyOperation) => boolean, detail: string): Factor | null => {
    const yes = average(data.filter(inGroup).map((row) => actual(row) as number))
    const no = average(data.filter((row) => !inGroup(row)).map((row) => actual(row) as number))
    if (yes === null || no === null) return null
    return { label, impact: yes - no, detail }
  }
  return [
    compare('Porsi di atas median', (row) => row.meals_prepared > median, `lebih dari ${median} porsi`),
    compare('Acara khusus', (row) => row.special_event, 'hari dengan acara khusus'),
    compare('Beban staf berat', (row) => row.meals_prepared / row.kitchen_staff > 35, 'lebih dari 35 porsi per staf'),
    compare('Akhir pekan', (row) => [0, 6].includes(parseDate(row.operation_date).getDay()), 'Sabtu dan Minggu'),
    compare('Staf berpengalaman', (row) => row.staff_experience === 'expert', 'staf ahli'),
  ]
    .filter((item): item is Factor => item !== null)
    .sort((a, b) => b.impact - a.impact)
}

export function experienceAverages(rows: DailyOperation[]) {
  return (['beginner', 'intermediate', 'expert'] as Experience[]).map((level) => ({
    level,
    label: experienceLabel[level],
    average: average(withActual(rows).filter((row) => row.staff_experience === level).map((row) => actual(row) as number)),
  }))
}

export function categoryShares(categories: Array<{ category: string | null; actual_waste_kg: number | null }>) {
  const items = categories.filter((item) => Number(item.actual_waste_kg) > 0)
  const total = items.reduce((sum, item) => sum + Number(item.actual_waste_kg), 0)
  if (!total) return { total: 0, items: [] as Array<{ label: string; value: number; kg: number; color: string }> }
  const merged = new Map<string, number>()
  items.forEach((item) => {
    const label = categoryLabel(item.category)
    merged.set(label, (merged.get(label) ?? 0) + Number(item.actual_waste_kg))
  })
  const list = [...merged.entries()].sort((a, b) => b[1] - a[1])
  // Pembulatan dengan sisa terbesar agar jumlah persen tepat 100.
  const raw = list.map(([, value]) => (value / total) * 100)
  const floors = raw.map(Math.floor)
  let rest = 100 - floors.reduce((sum, value) => sum + value, 0)
  raw.map((value, index) => ({ index, fraction: value - floors[index] }))
    .sort((a, b) => b.fraction - a.fraction)
    .forEach(({ index }) => { if (rest > 0) { floors[index] += 1; rest -= 1 } })
  return {
    total,
    items: list.map(([label, value], index) => ({ label, value: floors[index], kg: value, color: CATEGORY_COLORS[index % CATEGORY_COLORS.length] })),
  }
}

// ---------- Form input harian -------------------------------------------------------

export type DailyForm = {
  operation_date: string
  meals_prepared: string
  kitchen_staff: string
  staff_experience: Experience
  special_event: boolean
  event_type: string
  temperature_c: string
  humidity_percent: string
  previous_waste_kg: string
  waste_category: string
  actual_waste_kg: string
  manager_notes: string
}

const text = (value: number | string | null | undefined) => (value === null || value === undefined ? '' : String(value))

export function toForm(row: DailyFields): DailyForm {
  return {
    operation_date: row.operation_date,
    meals_prepared: text(row.meals_prepared),
    kitchen_staff: text(row.kitchen_staff),
    staff_experience: row.staff_experience,
    special_event: row.special_event,
    event_type: text(row.event_type),
    temperature_c: text(row.temperature_c),
    humidity_percent: text(row.humidity_percent),
    previous_waste_kg: text(row.previous_waste_kg),
    waste_category: text(row.waste_category),
    actual_waste_kg: text(row.actual_waste_kg),
    manager_notes: text(row.manager_notes),
  }
}

const decimal = (value: string) => (value.trim() === '' ? null : Number(value.replace(',', '.')))

export function fromForm(form: DailyForm): DailyFields {
  return {
    operation_date: form.operation_date,
    meals_prepared: Math.round(Number(form.meals_prepared)),
    kitchen_staff: Math.round(Number(form.kitchen_staff)),
    staff_experience: form.staff_experience,
    special_event: form.special_event,
    event_type: form.special_event && form.event_type.trim() ? form.event_type.trim() : null,
    temperature_c: decimal(form.temperature_c) ?? 0,
    humidity_percent: decimal(form.humidity_percent) ?? 0,
    previous_waste_kg: decimal(form.previous_waste_kg),
    waste_category: form.waste_category || null,
    actual_waste_kg: decimal(form.actual_waste_kg),
    manager_notes: form.manager_notes.trim() || null,
  }
}

/** Hanya 12 isian input harian (respons backend memuat kolom lain yang ditolak saat dikirim balik). */
export function fieldsOf(row: DailyFields): DailyFields {
  return {
    operation_date: row.operation_date,
    meals_prepared: Number(row.meals_prepared),
    kitchen_staff: Number(row.kitchen_staff),
    staff_experience: row.staff_experience,
    special_event: Boolean(row.special_event),
    event_type: row.event_type ?? null,
    temperature_c: Number(row.temperature_c),
    humidity_percent: Number(row.humidity_percent),
    previous_waste_kg: num(row.previous_waste_kg),
    waste_category: row.waste_category ?? null,
    actual_waste_kg: num(row.actual_waste_kg),
    manager_notes: row.manager_notes ?? null,
  }
}

/** Isian rencana dari data terakhir (tanpa limbah aktual) untuk tanggal baru. */
export function planFrom(template: DailyFields | null, date: string, previousWaste: number | null): DailyFields {
  return {
    operation_date: date,
    meals_prepared: template?.meals_prepared ?? 300,
    kitchen_staff: template?.kitchen_staff ?? 10,
    staff_experience: template?.staff_experience ?? 'intermediate',
    special_event: false,
    event_type: null,
    temperature_c: Number(template?.temperature_c ?? 28),
    humidity_percent: Number(template?.humidity_percent ?? 65),
    previous_waste_kg: previousWaste,
    waste_category: template?.waste_category ?? null,
    actual_waste_kg: null,
    manager_notes: null,
  }
}

// ---------- Data contoh untuk diunggah ---------------------------------------------

/**
 * CSV 30 hari terakhir (limbah aktual terisi) + hari ini (rencana tanpa aktual),
 * dengan tanggal mengikuti hari saat file diunduh. Rentang nilai mengikuti data latih
 * model; angka dibuat acak tetapi sama setiap kali untuk tanggal yang sama.
 */
export function sampleCsv(endDate = todayIso()) {
  const header = 'operation_date,meals_prepared,kitchen_staff,staff_experience,special_event,event_type,temperature_c,humidity_percent,previous_waste_kg,waste_category,actual_waste_kg,manager_notes'
  const rows: string[] = []
  let previous: number | null = null
  const categories = ['meat', 'vegetables', 'dairy', 'grains']
  const experiences: Experience[] = ['beginner', 'intermediate', 'intermediate', 'expert']
  for (let offset = -30; offset <= 0; offset += 1) {
    const date = addDays(endDate, offset)
    let seed = Number(date.replaceAll('-', '')) % 2147483647
    const random = () => {
      seed = (seed * 48271) % 2147483647
      return seed / 2147483647
    }
    const day = parseDate(date).getDay()
    const weekend = day === 0 || day === 6
    const event = random() < (weekend ? 0.3 : 0.08)
    const meals = Math.round((260 + random() * 160 + (weekend ? 60 : 0) + (event ? 90 : 0)) / 5) * 5
    const experience = experiences[Math.floor(random() * experiences.length)]
    const staff = Math.max(6, Math.min(18, Math.round(meals / (28 + random() * 12))))
    const temperature = (22 + random() * 10).toFixed(1)
    const humidity = (50 + random() * 30).toFixed(1)
    const load = meals / staff
    const waste = offset === 0 ? null
      : 18 + meals * 0.055 + (event ? 9 : 0) + (load > 35 ? 4 : 0) + (experience === 'beginner' ? 3 : experience === 'expert' ? -2 : 0) + (random() - 0.5) * 10
    const note = offset === 0 ? 'Rencana hari ini' : event ? 'Pesanan rombongan' : ''
    rows.push([
      date, meals, staff, experience, event, event ? (weekend ? 'Arisan keluarga' : 'Katering kantor') : '', temperature, humidity,
      previous === null ? '' : previous.toFixed(2), categories[Math.floor(random() * categories.length)], waste === null ? '' : waste.toFixed(2), note,
    ].join(','))
    previous = waste
  }
  return `${header}\n${rows.join('\n')}\n`
}

export function downloadText(content: string, filename: string, type = 'text/csv;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
