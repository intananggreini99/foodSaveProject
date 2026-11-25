'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  applyScenario, createScenario, getScenarioOptions, listOperations, listScenarios, predictOperation, previewPrediction,
  updateOperation, type DailyOperation, type Prediction, type Scenario, type ScenarioOptions,
} from '@/lib/api'
import { addDays, fieldsOf, kg, mediumDate, num, riskLabel, rupiah, shortDate, weekday } from '@/lib/format'
import { errorText, useApp } from './context'
import { bestOption } from './Overview'
import { Empty, Icon, selectClass } from './ui'

const round5 = (value: number) => Math.max(5, Math.round(value / 5) * 5)

/** Aturan frontend: makin besar pengurangan dari rencana awal, makin besar risiko kehabisan menu. */
function shortage(portions: number, baseline: number) {
  const cut = baseline ? (1 - portions / baseline) * 100 : 0
  return cut > 15.5 ? 'Tinggi' : cut >= 9.5 ? 'Sedang' : 'Rendah'
}

export default function SimulasiPorsi() {
  const { today, version, settings, focusDate, clearFocus, navigate, openDetail, fail, refresh, canEdit } = useApp()
  const [operations, setOperations] = useState<DailyOperation[] | null>(null)
  const [baseId, setBaseId] = useState<string | null>(null)
  const [options, setOptions] = useState<ScenarioOptions | null>(null)
  const [optionsError, setOptionsError] = useState<string | null>(null)
  const [saved, setSaved] = useState<Scenario[]>([])
  const [portions, setPortions] = useState(0)
  const [staff, setStaff] = useState(1)
  const [live, setLive] = useState<Prediction | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listOperations({ starts_on: addDays(today, -30), ends_on: addDays(today, 30), limit: 100 }).then((page) => {
      const items = [...page.items].sort((a, b) => a.operation_date.localeCompare(b.operation_date))
      setOperations(items)
      setBaseId((current) => {
        if (current && items.some((row) => row.id === current)) return current
        const wanted = focusDate ?? today
        const exact = items.find((row) => row.operation_date === wanted)
        const upcoming = items.find((row) => row.operation_date >= today)
        return (exact ?? upcoming ?? items[items.length - 1])?.id ?? null
      })
      if (focusDate) clearFocus()
    }).catch((error) => { setOperations([]); fail('Data harian belum dapat dimuat', error) })
  }, [today, version, focusDate, clearFocus, fail])

  const base = useMemo(() => operations?.find((row) => row.id === baseId) ?? null, [operations, baseId])

  useEffect(() => {
    if (!base) return
    setPortions(base.meals_prepared)
    setStaff(base.kitchen_staff)
    listScenarios(base.id).then(setSaved).catch(() => setSaved([]))
  }, [base])

  // Empat pilihan 0/5/10/15% dari backend (dihitung ulang saat jumlah staf diubah).
  useEffect(() => {
    if (!base) return
    const timer = window.setTimeout(() => {
      getScenarioOptions(base.id, staff === base.kitchen_staff ? null : staff)
        .then((value) => { setOptions(value); setOptionsError(null) })
        .catch((error) => { setOptions(null); setOptionsError(errorText(error)) })
    }, 350)
    return () => window.clearTimeout(timer)
  }, [base, staff])

  // Titik pilihan saat slider digeser: pratinjau model (tidak disimpan).
  useEffect(() => {
    if (!base || !portions || !staff) return
    const timer = window.setTimeout(() => {
      previewPrediction({
        operation_date: base.operation_date, meals_prepared: portions, kitchen_staff: staff, staff_experience: base.staff_experience,
        special_event: base.special_event, temperature_c: Number(base.temperature_c), humidity_percent: Number(base.humidity_percent),
      }).then(setLive).catch(() => setLive(null))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [base, portions, staff])

  if (operations === null) return <div className="page-enter"><article className="card text-sm text-slate-500">Memuat data harian...</article></div>
  if (!base) return <div className="page-enter"><div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">Belum ada rencana untuk disimulasikan</h1><p className="mt-1 text-sm text-slate-500">Simulasi porsi memakai rencana harian yang sudah tersimpan.</p></div><article className="card"><Empty>Simpan rencana di Input Data Harian (atau unggah file CSV), lalu kembali ke halaman ini untuk membandingkan pengurangan porsi 5%, 10%, dan 15%.</Empty><button onClick={() => navigate('Input Data Harian', today)} className="mt-4 rounded-xl bg-[#173d32] px-5 py-3 text-sm font-semibold text-white">Buka Input Data Harian</button></article></div>

  const baseline = base.meals_prepared
  const min = round5(baseline * 0.7)
  const max = Math.max(min + 10, round5(baseline * 1.15))
  const staffMin = Math.max(1, base.kitchen_staff - 6)
  const staffMax = base.kitchen_staff + 8
  const cost = Number(settings?.ingredient_cost_per_kg ?? 0)
  const baselineWaste = num(options?.baseline_waste_kg)
  const liveWaste = num(live?.predicted_waste_kg)
  const saving = baselineWaste !== null && liveWaste !== null ? Math.max(0, baselineWaste - liveWaste) * cost : null
  const perStaff = Math.round(portions / staff)
  const risk = shortage(portions, baseline)
  const best = bestOption(options)
  const preset = options?.options.find((item) => item.simulated_portions === portions && item.kitchen_staff === staff) ?? null
  const unchanged = portions === baseline && staff === base.kitchen_staff
  const target = base.operation_date === today ? 'Jadikan Rencana Hari Ini' : `Terapkan ke ${shortDate(base.operation_date)}`

  // Grafik porsi vs limbah.
  const safe = Number(settings?.safe_max_kg ?? 0)
  const warning = Number(settings?.warning_max_kg ?? 0)
  const points = [...(options?.options ?? [])].map((item) => [item.simulated_portions, Number(item.predicted_waste_kg)] as const).sort((a, b) => a[0] - b[0])
  const top = Math.max(warning * 1.2, ...points.map((p) => p[1]), liveWaste ?? 0, 10)
  const step = top > 80 ? 20 : top > 40 ? 10 : 5
  const chartMax = Math.ceil(top / step) * step
  const sx = (p: number) => 75 + ((Math.min(max, Math.max(min, p)) - min) / (max - min)) * 485
  const sy = (w: number) => 220 - (Math.min(w, chartMax) / chartMax) * 195
  const ticks = Array.from({ length: 5 }, (_, i) => round5(min + ((max - min) * i) / 4))

  async function save() {
    if (!preset || !base) return
    setBusy(true)
    try {
      const row = await createScenario({ daily_operation_id: base.id, reduction_percent: preset.reduction_percent, kitchen_staff: staff === base.kitchen_staff ? null : staff, application_date: base.operation_date, notes: `Simulasi ${portions} porsi, ${staff} staf`, status: 'saved' })
      setSaved([row, ...saved])
      openDetail('Skenario tersimpan', `Skenario ${row.simulated_portions} porsi dan ${row.kitchen_staff} staf untuk ${mediumDate(row.application_date)} disimpan. Perkiraan limbah ${kg(row.predicted_waste_kg)} kg, hemat ${kg(row.savings_kg)} kg (${rupiah(row.savings_amount)}).`)
    } catch (error) {
      fail('Skenario belum tersimpan', error)
    } finally {
      setBusy(false)
    }
  }

  async function apply() {
    if (!base) return
    setBusy(true)
    try {
      let predicted: number | null = null
      if (preset && options) {
        const row = await createScenario({ daily_operation_id: base.id, reduction_percent: preset.reduction_percent, kitchen_staff: staff === base.kitchen_staff ? null : staff, application_date: base.operation_date, notes: `Diterapkan dari Simulasi Porsi`, status: 'saved' })
        const result = await applyScenario(row.id, options.operation_version)
        predicted = num(result.prediction?.predicted_waste_kg)
      } else {
        await updateOperation(base.id, { ...fieldsOf(base), meals_prepared: portions, kitchen_staff: staff, expected_version: base.version, correction_reason: `Simulasi porsi: ${portions} porsi, ${staff} staf` })
        predicted = num((await predictOperation(base.id)).predicted_waste_kg)
      }
      refresh()
      navigate('Input Data Harian', base.operation_date)
      openDetail('Rencana dibawa ke Input Data Harian', `Rencana ${mediumDate(base.operation_date)} kini ${portions} porsi dan ${staff} staf, dengan perkiraan limbah ${kg(predicted)} kg. Periksa kondisi operasional lalu catat limbah aktual setelah layanan selesai.`)
    } catch (error) {
      fail('Rencana belum dapat diterapkan', error)
    } finally {
      setBusy(false)
    }
  }

  const tips: Record<string, string> = {
    Prediksi: live ? `Model memperkirakan ${kg(live.predicted_waste_kg)} kg (rentang ${kg(live.interval_lower_kg)}–${kg(live.interval_upper_kg)} kg) untuk ${portions} porsi dan ${staff} staf.${live.outside_training_range ? ' Beberapa isian di luar rentang data latih model.' : ''}` : 'Pratinjau belum tersedia.',
    Hemat: `Dibanding rencana awal ${baseline} porsi (${kg(baselineWaste)} kg), pilihan ini menghemat ${kg(baselineWaste !== null && liveWaste !== null ? Math.max(0, baselineWaste - liveWaste) : null)} kg atau ${rupiah(saving)} dengan harga bahan ${rupiah(cost)}/kg.`,
    'Beban staf': `${portions} porsi dibagi ${staff} staf = ${perStaff} porsi per staf. Di atas 35 porsi per staf, pertimbangkan menambah staf.`,
    'Risiko kehabisan': `Rencana ini ${Math.round((1 - portions / baseline) * 100)}% dari rencana awal. Pengurangan di bawah 10% berisiko rendah, 10–15% sedang, lebih dari 15% tinggi (aturan frontend, bukan hasil model).`,
  }

  return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">{best ? `${best.simulated_portions} porsi paling seimbang: hemat ${rupiah(best.savings_amount)}` : options ? `Rencana ${baseline} porsi sudah paling seimbang` : 'Menghitung pilihan porsi...'}</h1><p className="mt-1 text-sm text-slate-500">Rencana dasar {weekday(base.operation_date)}, {mediumDate(base.operation_date)}: {baseline} porsi, {base.kitchen_staff} staf. Coba jumlah porsi dan staf untuk mencari rencana paling aman.</p></div>
    {optionsError && <div className="mb-4 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"><Icon name="alert"/>{optionsError}</div>}
    <div className="grid gap-4 lg:grid-cols-[.72fr_1.28fr]"><article className="card"><h2 className="section-title">Atur Porsi & Staf</h2><label className="mt-4 block"><span className="mb-2 block text-xs font-semibold text-slate-600">Rencana dasar</span><select value={base.id} onChange={(event) => setBaseId(event.target.value)} className={selectClass}>{operations.map((row) => <option key={row.id} value={row.id}>{weekday(row.operation_date)}, {mediumDate(row.operation_date)} · {row.meals_prepared} porsi</option>)}</select></label><p className="mt-7 text-center text-5xl font-bold text-[#173d32]">{portions}</p><p className="mt-2 text-center text-xs text-slate-400">porsi direncanakan</p><input aria-label="Jumlah porsi" type="range" min={min} max={max} step="5" value={portions} onChange={(e) => setPortions(+e.target.value)} className="mt-6 w-full accent-[#2d826b]"/><div className="mt-2 flex justify-between text-[10px] text-slate-400"><span>{min}</span><span>{max}</span></div><div className="mt-5 flex justify-between text-xs"><span>Jumlah staf</span><strong>{staff} orang</strong></div><input aria-label="Jumlah staf" type="range" min={staffMin} max={staffMax} value={staff} onChange={(e) => setStaff(+e.target.value)} className="mt-3 w-full accent-[#2d826b]"/><div className="mt-5 grid grid-cols-4 gap-2">{(options?.options ?? []).map((item) => <button onClick={() => setPortions(item.simulated_portions)} key={item.reduction_percent} className={`rounded-lg py-2 text-[10px] font-semibold hover:bg-emerald-100 ${portions === item.simulated_portions ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100'}`}>{item.reduction_percent === 0 ? 'Awal' : `-${item.reduction_percent}%`}</button>)}</div></article>
    <article className="card"><div className="flex justify-between"><div><h2 className="section-title">Porsi vs Limbah</h2><p className="section-subtitle">Sumbu X: porsi · Sumbu Y: limbah (kg)</p></div><span className="h-fit rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">Hemat {rupiah(saving)}</span></div><svg viewBox="0 0 620 250" className="mt-4 w-full">{settings && <><rect x="50" y={sy(chartMax)} width="540" height={sy(warning) - sy(chartMax)} fill="#fee2e2" opacity=".6"/><rect x="50" y={sy(warning)} width="540" height={sy(safe) - sy(warning)} fill="#fef3c7" opacity=".7"/><rect x="50" y={sy(safe)} width="540" height={220 - sy(safe)} fill="#dcfce7" opacity=".6"/></>}{Array.from({ length: chartMax / step }, (_, i) => (i + 1) * step).map((v) => <g key={v}><line x1="50" y1={sy(v)} x2="590" y2={sy(v)} stroke="#dce3df"/><text x="42" y={sy(v) + 4} textAnchor="end" fontSize="9">{v} kg</text></g>)}{points.length > 1 && <path d={points.map(([p, w], i) => `${i ? 'L' : 'M'}${sx(p)} ${sy(w)}`).join(' ')} fill="none" stroke="#27715f" strokeWidth="4"/>}{points.map(([p, w]) => <circle key={p} cx={sx(p)} cy={sy(w)} r="5" fill="white" stroke="#27715f" strokeWidth="3"/>)}{liveWaste !== null && <><circle cx={sx(portions)} cy={sy(liveWaste)} r="8" fill="#e99a3d" stroke="white" strokeWidth="3"/><text x={sx(portions)} y={sy(liveWaste) - 15} textAnchor="middle" fontSize="9" fontWeight="700">Pilihan: {kg(liveWaste)} kg</text></>}{ticks.map((p) => <text key={p} x={sx(p)} y="240" textAnchor="middle" fontSize="9">{p}</text>)}</svg></article></div>
    {risk === 'Tinggi' && <div className="mt-4 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><Icon name="alert"/>Porsi terlalu sedikit bisa membuat pelanggan kehabisan menu.</div>}
    <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">{[['Prediksi', liveWaste === null ? '-' : `${kg(liveWaste)} kg`], ['Hemat', rupiah(saving)], ['Beban staf', `${perStaff} porsi/orang`], ['Risiko kehabisan', risk]].map((x) => <article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-xl text-[#173d32]">{x[1]}</strong><button onClick={() => openDetail(x[0], tips[x[0]])} className="mt-3 text-[10px] font-bold text-emerald-700">Lihat saran</button></article>)}</div>
    <article className="card mt-4 overflow-x-auto"><h2 className="section-title">Perbandingan 4 Skenario</h2>{options ? <table className="mt-4 w-full min-w-[620px] text-left text-xs"><thead><tr className="text-slate-400">{['Skenario', 'Porsi', 'Limbah', 'Hemat', 'Risiko limbah', 'Risiko kehabisan'].map((x) => <th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{options.options.map((item) => { const status = saved.find((row) => Number(row.reduction_percent) === item.reduction_percent && row.kitchen_staff === item.kitchen_staff && row.status !== 'draft')?.status; return <tr className="border-t border-slate-100" key={item.reduction_percent}><td className="py-3">{item.reduction_percent === 0 ? 'Awal' : `−${item.reduction_percent}%`}{status && <span className="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">{status === 'applied' ? 'diterapkan' : 'tersimpan'}</span>}</td><td className="py-3">{item.simulated_portions}</td><td className="py-3">{kg(item.predicted_waste_kg)} kg</td><td className="py-3">{rupiah(Math.max(0, Number(item.savings_amount)))}</td><td className="py-3">{riskLabel[item.risk_level]}</td><td className="py-3">{shortage(item.simulated_portions, baseline)}</td></tr> })}</tbody></table> : <div className="mt-4"><Empty>{optionsError ?? 'Menghitung empat skenario...'}</Empty></div>}<div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-[10px] text-slate-400">Ini perkiraan model {options?.model_version ?? ''}, bukan jaminan.{!preset && !unchanged ? ' Pilih salah satu dari 4 skenario untuk menyimpan skenario.' : ''}</p><div className="flex gap-2"><button disabled={busy || !preset || !canEdit} onClick={save} className="rounded-lg border px-3 py-2 text-xs font-bold disabled:opacity-50">Simpan Skenario</button><button disabled={busy || unchanged || !canEdit} onClick={apply} className="rounded-lg bg-[#173d32] px-3 py-2 text-xs font-bold text-white disabled:opacity-50">{busy ? 'Memproses...' : target}</button></div></div></article>
  </div>
}
