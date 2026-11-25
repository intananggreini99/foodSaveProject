'use client'

import { useState, type ReactNode } from 'react'
import type { Settings, TrendPoint } from '@/lib/api'
import { addDays, daysBetween, kg, mediumDate, num, shortDate } from '@/lib/format'

export type IconName =
  | 'grid' | 'chart' | 'spark' | 'database' | 'settings' | 'bell' | 'calendar' | 'arrow'
  | 'leaf' | 'menu' | 'close' | 'trend' | 'check' | 'alert' | 'chevron'

const paths: Record<IconName, ReactNode> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></>,
  chart: <><path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/></>,
  spark: <><path d="m13 2-1.7 5.2a2 2 0 0 1-1.3 1.3L5 10l5 1.6a2 2 0 0 1 1.3 1.3L13 18l1.6-5.1a2 2 0 0 1 1.3-1.3L21 10l-5.1-1.5a2 2 0 0 1-1.3-1.3L13 2Z"/><path d="m5 16-.6 1.8a1 1 0 0 1-.6.6L2 19l1.8.6a1 1 0 0 1 .6.6L5 22l.6-1.8a1 1 0 0 1 .6-.6L8 19l-1.8-.6a1 1 0 0 1-.6-.6L5 16Z"/></>,
  database: <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-2.8 2.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.6v.2h-4V21a1.7 1.7 0 0 0-1-1.6 1.7 1.7 0 0 0-1.9.3l-.1.1L4.2 17l.1-.1a1.7 1.7 0 0 0 .3-1.9A1.7 1.7 0 0 0 3 14H2.8v-4H3a1.7 1.7 0 0 0 1.6-1 1.7 1.7 0 0 0-.3-1.9L4.2 7 7 4.2l.1.1A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.6v-.2h4V3a1.7 1.7 0 0 0 1 1.6 1.7 1.7 0 0 0 1.9-.3l.1-.1L19.8 7l-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.6 1h.2v4H21a1.7 1.7 0 0 0-1.6 1Z"/></>,
  bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 7h18s-3 0-3-7"/><path d="M13.7 19a2 2 0 0 1-3.4 0"/></>,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></>,
  arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
  leaf: <><path d="M20 4C13 4 6 7 5 14c-.3 2.1 1 4 3 4 7 0 10-7 12-14Z"/><path d="M4 21c2-6 6-9 12-12"/></>,
  menu: <path d="M4 6h16M4 12h16M4 18h16"/>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  trend: <path d="m3 17 6-6 4 4 8-9M15 6h6v6"/>,
  check: <path d="m5 12 4 4L19 6"/>,
  alert: <><path d="M12 9v4M12 17h.01"/><path d="M10.3 3.7 2.4 18a2 2 0 0 0 1.8 3h15.6a2 2 0 0 0 1.8-3L13.7 3.7a2 2 0 0 0-3.4 0Z"/></>,
  chevron: <path d="m9 18 6-6-6-6"/>,
}

export function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

/** Field bergaya sama dengan desain awal, tetapi terkendali (controlled). */
export function Field({ label, value, onChange, suffix, type = 'text', readOnly, placeholder, step, min, max }: {
  label: string
  value: string
  onChange?: (value: string) => void
  suffix?: string
  type?: string
  readOnly?: boolean
  placeholder?: string
  step?: string
  min?: string
  max?: string
}) {
  return <label className="block"><span className="mb-2 block text-xs font-semibold text-slate-600">{label}</span><div className={`flex rounded-xl border border-slate-200 px-3 py-2.5 focus-within:border-emerald-500 ${readOnly ? 'bg-slate-50' : 'bg-white'}`}><input type={type} value={value} readOnly={readOnly} placeholder={placeholder} step={step} min={min} max={max} onChange={(event) => onChange?.(event.target.value)} className="min-w-0 flex-1 bg-transparent text-sm outline-none"/>{suffix && <span className="text-xs text-slate-400">{suffix}</span>}</div></label>
}

export const selectClass = 'w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm'

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-500">{children}</p>
}

export type Slice = { label: string; value: number; color: string }

export function Donut({ composition }: { composition: Slice[] }) {
  let offset = 0
  return <div className="h-40 w-40 shrink-0">
    <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90 drop-shadow-sm" role="img" aria-label="Donat proporsi kategori limbah">
      <circle cx="60" cy="60" r="43" fill="none" stroke="#edf1ee" strokeWidth="18"/>
      {composition.map(({ value, color }, index) => { const start = offset; offset += value; return <circle className="donut-segment" key={index} cx="60" cy="60" r="43" fill="none" stroke={color} strokeWidth="18" strokeDasharray={`${Math.max(0, value * 2.701 - 2)} 270.1`} strokeDashoffset={-start * 2.701}/> })}
      <circle cx="60" cy="60" r="28" fill="white"/>
      <text x="60" y="58" textAnchor="middle" fill="#173d32" fontSize="12" fontWeight="700" transform="rotate(90 60 60)">{composition.length ? '100%' : '0%'}</text>
      <text x="60" y="70" textAnchor="middle" fill="#94a3b8" fontSize="6" transform="rotate(90 60 60)">{composition.length ? 'total' : 'belum ada'}</text>
    </svg>
  </div>
}

function niceStep(max: number) {
  const raw = max / 5
  const power = 10 ** Math.floor(Math.log10(raw))
  const unit = [1, 2, 2.5, 5, 10].find((candidate) => candidate * power >= raw) ?? 10
  return unit * power
}

/** Grafik aktual vs prediksi tersimpan dari GET /dashboard/trend. */
export function TrendChart({ series, startsOn, endsOn, settings, mae }: {
  series: TrendPoint[]
  startsOn: string
  endsOn: string
  settings: Pick<Settings, 'safe_max_kg' | 'warning_max_kg'> | null
  mae: number | null
}) {
  const [hover, setHover] = useState<number | null>(null)
  const span = Math.max(1, daysBetween(startsOn, endsOn))
  const points = series.map((item) => ({
    date: item.date,
    index: daysBetween(startsOn, item.date),
    actual: num(item.actual_waste_kg),
    predicted: num(item.predicted_waste_kg),
    lower: num(item.interval_lower_kg),
    upper: num(item.interval_upper_kg),
  }))
  const safe = Number(settings?.safe_max_kg ?? 0)
  const warning = Number(settings?.warning_max_kg ?? 0)
  const values = points.flatMap((p) => [p.actual, p.predicted, p.upper]).filter((v): v is number => v !== null)
  const top = Math.max(warning * 1.2, ...values, 10)
  const step = niceStep(top)
  const chartMax = Math.ceil(top / step) * step
  const x = (index: number) => 58 + index * (712 / span)
  const y = (value: number) => 250 - (Math.min(value, chartMax) / chartMax) * 210
  const line = (key: 'actual' | 'predicted') => {
    let path = ''
    let previous: number | null = null
    points.forEach((p) => {
      const value = p[key]
      if (value === null) { previous = null; return }
      path += `${previous === null || p.index - previous > 1 ? 'M' : 'L'}${x(p.index).toFixed(1)},${y(value).toFixed(1)} `
      previous = p.index
    })
    return path.trim()
  }
  const banded = points.filter((p) => p.lower !== null && p.upper !== null)
  const band = banded.length > 1 ? [...banded.map((p) => `${x(p.index)},${y(p.upper as number)}`), ...[...banded].reverse().map((p) => `${x(p.index)},${y(p.lower as number)}`)].join(' ') : ''
  const gaps = points
    .filter((p) => p.actual !== null && p.predicted !== null)
    .map((p) => ({ ...p, gap: Math.abs((p.actual as number) - (p.predicted as number)) }))
    .sort((a, b) => b.gap - a.gap)
    .reduce<Array<{ index: number; actual: number | null; predicted: number | null; gap: number }>>((picked, p) => (picked.length < 2 && picked.every((q) => Math.abs(q.index - p.index) >= Math.max(3, span / 8)) ? [...picked, p] : picked), [])
  const labels = Array.from({ length: 7 }, (_, i) => Math.round((i * span) / 6))
  const active = hover === null ? null : points[hover]
  const tipX = active ? Math.min(640, Math.max(65, x(active.index) - 62)) : 0
  return <div className="mt-5 w-full overflow-hidden">
    <div className="mb-2 flex flex-wrap gap-4 text-[10px] text-slate-500"><span className="flex items-center gap-2"><i className="h-0.5 w-5 bg-[#27715f]"/>Aktual</span><span className="flex items-center gap-2"><i className="h-0 w-5 border-t-2 border-dashed border-orange-400"/>Prediksi</span><span className="flex items-center gap-2"><i className="h-2 w-5 bg-slate-200"/>Rentang perkiraan</span></div>
    <svg viewBox="0 0 800 285" className="h-auto min-h-[245px] w-full" role="img" aria-label="Perbandingan aktual dan prediksi limbah dalam kilogram">
      {settings && <><rect x="58" y={y(chartMax)} width="712" height={y(warning) - y(chartMax)} fill="#fee2e2" opacity=".55"/><rect x="58" y={y(warning)} width="712" height={y(safe) - y(warning)} fill="#fef3c7" opacity=".7"/><rect x="58" y={y(safe)} width="712" height={y(0) - y(safe)} fill="#dcfce7" opacity=".55"/></>}
      {Array.from({ length: Math.round(chartMax / step) + 1 }, (_, i) => i * step).map((v) => <g key={v}><line x1="58" y1={y(v)} x2="770" y2={y(v)} stroke="#dce3df"/><text x="48" y={y(v) + 4} textAnchor="end" fontSize="9" fill="#82908a">{v} kg</text></g>)}
      <text x="14" y="145" transform="rotate(-90 14 145)" fontSize="9" fill="#82908a">Limbah (kg)</text>
      {band && <polygon points={band} fill="#94a3b8" opacity=".18"/>}
      <path className="chart-line chart-line-dashed" d={line('predicted')} fill="none" stroke="#e99a3d" strokeWidth="2.5" strokeDasharray="7 6"/>
      <path className="chart-line" d={line('actual')} fill="none" stroke="#27715f" strokeWidth="3"/>
      {points.map((p, i) => p.predicted !== null && p.actual === null && <circle key={`p${i}`} cx={x(p.index)} cy={y(p.predicted)} r={hover === i ? 5 : 3} fill="#e99a3d" tabIndex={0} className="chart-point" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}/>)}
      {points.map((p, i) => p.actual !== null && <circle className="chart-point" tabIndex={0} key={i} cx={x(p.index)} cy={y(p.actual)} r={hover === i ? 6 : 4} fill="white" stroke="#27715f" strokeWidth="2" onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}/>)}
      {labels.map((i) => <text key={i} x={x(i)} y="270" textAnchor="middle" fontSize="9" fill="#82908a">{shortDate(addDays(startsOn, i))}</text>)}
      <text x="414" y="283" textAnchor="middle" fontSize="9" fill="#82908a">Tanggal</text>
      {gaps.map((p) => { const top = Math.max(p.actual as number, p.predicted as number); return <g key={`g${p.index}`}><line x1={x(p.index)} y1={y(top) - 5} x2={x(p.index)} y2={Math.max(14, y(top) - 28)} stroke="#b45309"/><rect x={x(p.index) - 37} y={Math.max(0, y(top) - 47)} width="74" height="20" rx="6" fill="#fff7ed"/><text x={x(p.index)} y={Math.max(13, y(top) - 34)} textAnchor="middle" fontSize="8" fontWeight="700" fill="#b45309">Selisih {kg(p.gap)} kg</text></g> })}
      {!points.length && <text x="414" y="140" textAnchor="middle" fontSize="11" fill="#82908a">Belum ada data operasional pada periode ini</text>}
      {active && <g><rect x={tipX} y="10" width="135" height="57" rx="8" fill="#173d32"/><text x={tipX + 9} y="26" fontSize="8" fill="white">{mediumDate(active.date)}</text><text x={tipX + 9} y="40" fontSize="8" fill="#d1fae5">Aktual {kg(active.actual)} kg · Prediksi {kg(active.predicted)} kg</text><text x={tipX + 9} y="54" fontSize="8" fill="#fdba74">{active.actual !== null && active.predicted !== null ? `Selisih ${kg(Math.abs(active.actual - active.predicted))} kg` : active.actual === null ? 'Limbah aktual belum dicatat' : 'Belum ada prediksi tersimpan'}</text></g>}
    </svg>
    <p className="mt-2 text-[11px] text-slate-400">{mae !== null ? `Prediksi rata-rata meleset ±${kg(mae)} kg pada periode ini.` : 'Belum ada pasangan limbah aktual dan prediksi tersimpan untuk menghitung selisih.'}</p>
  </div>
}
