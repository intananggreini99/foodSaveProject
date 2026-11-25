'use client'

import { useEffect, useState } from 'react'
import { createPlan, getPlan, listOperations, listPlans, updatePlanDay, type WeeklyPlan } from '@/lib/api'
import { addDays, fieldsOf, kg, num, planFrom, riskLabel, rupiah, shortDate, weekday } from '@/lib/format'
import { useApp } from './context'
import { Empty, Field, Icon } from './ui'

type DayEdit = { meals: string; staff: string; temperature: string; event: boolean; reason: string }

export default function Prediksi7Hari() {
  const { today, version, settings, openDetail, fail, refresh, canEdit } = useApp()
  const [plans, setPlans] = useState<WeeklyPlan[] | null>(null)
  const [planId, setPlanId] = useState<string | null>(null)
  const [plan, setPlan] = useState<WeeklyPlan | null>(null)
  const [selectedDay, setSelectedDay] = useState(0)
  const [edit, setEdit] = useState<DayEdit | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    listPlans().then((items) => {
      setPlans(items)
      setPlanId((current) => {
        if (current && items.some((item) => item.id === current)) return current
        const covering = items.find((item) => item.starts_on <= today && today <= addDays(item.starts_on, 6))
        return (covering ?? items[0])?.id ?? null
      })
    }).catch((error) => { setPlans([]); fail('Rencana 7 hari belum dapat dimuat', error) })
  }, [today, version, fail])

  useEffect(() => {
    if (!planId) { setPlan(null); return }
    getPlan(planId).then((detail) => {
      setPlan(detail)
      const index = detail.days?.findIndex((day) => day.prediction_date === today) ?? -1
      setSelectedDay(index >= 0 ? index : 0)
    }).catch((error) => fail('Rencana belum dapat dimuat', error))
  }, [planId, version, today, fail])

  const days = plan?.days ?? []
  const day = days[selectedDay]
  useEffect(() => {
    if (!day) { setEdit(null); return }
    const input = day.input_snapshot
    setEdit({ meals: String(input.meals_prepared), staff: String(input.kitchen_staff), temperature: String(input.temperature_c), event: input.special_event, reason: '' })
  }, [day])

  async function createNew() {
    setBusy(true)
    try {
      const covering = (plans ?? []).some((item) => item.starts_on <= today && today <= addDays(item.starts_on, 6))
      const latestEnd = (plans ?? []).map((item) => addDays(item.starts_on, 6)).sort().pop()
      const start = covering && latestEnd ? addDays(latestEnd > today ? latestEnd : today, 1) : today
      const template = (await listOperations({ limit: 1 })).items[0] ?? null
      const created = await createPlan({
        title: `Rencana ${shortDate(start)} – ${shortDate(addDays(start, 6))}`,
        starts_on: start,
        days: Array.from({ length: 7 }, (_, index) => planFrom(template, addDays(start, index), null)),
      })
      setPlanId(created.id)
      openDetail('Rencana 7 hari dibuat', `${created.title} memakai isian dari data harian terakhir${template ? ` (${template.meals_prepared} porsi, ${template.kitchen_staff} staf)` : ''}. Sesuaikan porsi, staf, suhu, dan acara khusus per hari di panel Ubah rencana.`)
      refresh()
    } catch (error) {
      fail('Rencana belum dapat dibuat', error)
    } finally {
      setBusy(false)
    }
  }

  async function saveDay() {
    if (!plan || !day || !edit) return
    setBusy(true)
    try {
      const input = fieldsOf(day.input_snapshot)
      const updated = await updatePlanDay(plan.id, day.id, {
        ...input,
        meals_prepared: Math.round(Number(edit.meals)),
        kitchen_staff: Math.round(Number(edit.staff)),
        temperature_c: Number(edit.temperature.replace(',', '.')),
        special_event: edit.event,
        event_type: edit.event ? input.event_type : null,
        expected_version: day.version,
        correction_reason: edit.reason.trim() || `Penyesuaian rencana ${weekday(day.prediction_date)}`,
      })
      setPlan(updated)
      const fresh = updated.days?.find((item) => item.id === day.id)
      openDetail('Rencana hari diperbarui', `${weekday(day.prediction_date)}, ${shortDate(day.prediction_date)} kini memakai rencana ${edit.meals} porsi dan ${edit.staff} staf. Prediksi baru ${kg(fresh?.prediction?.predicted_waste_kg)} kg (${fresh?.prediction ? riskLabel[fresh.prediction.risk_level] : '-'}).`)
    } catch (error) {
      fail('Perubahan belum tersimpan', error)
    } finally {
      setBusy(false)
    }
  }

  const safe = Number(settings?.safe_max_kg ?? 0)
  const warning = Number(settings?.warning_max_kg ?? 0)
  const cost = Number(settings?.ingredient_cost_per_kg ?? 0)
  const values = days.map((item) => num(item.prediction?.predicted_waste_kg) ?? 0)
  const max = Math.max(...values, warning, 1)
  const highDays = days.filter((item) => item.prediction?.risk_level === 'high').map((item) => weekday(item.prediction_date))
  const warnDays = days.filter((item) => item.prediction?.risk_level === 'warning').map((item) => weekday(item.prediction_date))
  const join = (names: string[]) => (names.length > 1 ? `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}` : names[0])
  const totalWaste = values.reduce((sum, value) => sum + value, 0)
  // Harga bahan terkini dari Pengaturan (prediksi lama mungkin dibuat saat harga masih 0).
  const totalCost = totalWaste * cost
  const excess = values.reduce((sum, value) => sum + Math.max(0, value - safe), 0) * cost
  const title = !plan ? (plans === null ? 'Memuat rencana...' : 'Belum ada rencana 7 hari') : highDays.length ? `${join(highDays)} berisiko Tinggi` : warnDays.length ? `${join(warnDays)} perlu diwaspadai` : 'Semua hari berisiko Aman'

  return <div className="page-enter">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-bold sm:text-[30px]">{title}</h1><p className="mt-1 text-sm text-slate-500">{plan ? <>Potensi hemat minggu ini <strong className="text-emerald-700">{rupiah(excess)}</strong> bila limbah tiap hari ditekan ke batas Aman.</> : 'Buat rencana untuk melihat prediksi limbah tujuh hari mulai hari ini.'}</p></div><div className="flex flex-wrap items-center gap-2">{(plans?.length ?? 0) > 1 && <select value={planId ?? ''} onChange={(event) => setPlanId(event.target.value)} className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-xs font-semibold">{plans?.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}</select>}{canEdit && <button disabled={busy} onClick={createNew} className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-semibold disabled:opacity-60">{busy && !plan ? 'Membuat...' : 'Buat Rencana Baru'}</button>}{plan && <button onClick={() => window.print()} className="rounded-xl bg-[#173d32] px-4 py-3 text-xs font-semibold text-white">Ekspor Rencana PDF</button>}</div></div>
    {!plan ? <article className="card"><Empty>{plans === null ? 'Memuat...' : 'Rencana 7 hari berisi tujuh tanggal berurutan. Setiap tanggal langsung diprediksi oleh model aktif, lalu bisa diubah satu per satu. Isian awal diambil dari data harian terakhir.'}</Empty>{plans !== null && canEdit && <button disabled={busy} onClick={createNew} className="mt-4 rounded-xl bg-[#173d32] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{busy ? 'Membuat rencana...' : 'Buat Rencana 7 Hari'}</button>}</article> : <>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">{days.map((d, i) => { const risk = d.prediction ? riskLabel[d.prediction.risk_level] : 'Waspada'; return <button key={d.id} onClick={() => setSelectedDay(i)} className={`rounded-2xl border p-4 text-left transition ${i === selectedDay ? 'ring-2 ring-[#173d32]' : ''} ${risk === 'Tinggi' ? 'border-red-200 bg-red-50' : risk === 'Aman' ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}><p className="text-xs text-slate-500">{weekday(d.prediction_date)} · {shortDate(d.prediction_date)}</p><strong className="mt-3 block text-2xl">{kg(d.prediction?.predicted_waste_kg)} kg</strong><span className={`mt-2 inline-block rounded-full px-2 py-1 text-[10px] font-bold ${risk === 'Tinggi' ? 'bg-red-100 text-red-700' : risk === 'Aman' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{d.prediction ? risk : 'Belum ada'}</span><p className="mt-3 text-[10px] text-slate-500">Rencana {d.input_snapshot.meals_prepared} porsi<br/>{Math.round(d.input_snapshot.meals_prepared / d.input_snapshot.kitchen_staff)} porsi/staf{d.input_snapshot.special_event ? ' · acara' : ''}</p></button> })}</div>
    <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_.6fr]"><article className="card"><h2 className="section-title">Limbah 7 Hari Mendatang</h2><div className="mt-6 flex h-64 items-end gap-3 border-b border-slate-200">{days.map((d, i) => { const value = values[i]; const level = d.prediction?.risk_level; return <div className="flex h-full flex-1 flex-col items-center justify-end gap-2" key={d.id}><span className="text-xs font-bold">{kg(value, 0)}</span><div className={`chart-bar w-full max-w-14 rounded-t-lg ${level === 'high' ? 'bg-red-400' : level === 'warning' ? 'bg-amber-400' : 'bg-emerald-500'}`} style={{ height: `${(value / max) * 200}px` }}/><span className="text-[10px] text-slate-400">{weekday(d.prediction_date)}</span></div> })}</div><div className="mt-4 flex flex-wrap gap-4 text-[10px] text-slate-500"><span>Hijau: Aman ≤{kg(safe)} kg</span><span>Kuning: Waspada {kg(safe)}–{kg(warning)} kg</span><span>Merah: Tinggi &gt;{kg(warning)} kg</span></div></article>
    <article className="card"><h2 className="section-title">Ubah rencana {day ? weekday(day.prediction_date) : ''}</h2><p className="section-subtitle">Simpan untuk menghitung ulang prediksi hari ini saja</p>{edit && <><div className="mt-5 space-y-4"><Field label="Porsi" type="number" min="0" value={edit.meals} onChange={(meals) => setEdit({ ...edit, meals })}/><Field label="Staf" type="number" min="1" value={edit.staff} onChange={(staff) => setEdit({ ...edit, staff })}/><Field label="Suhu" type="number" step="0.1" value={edit.temperature} onChange={(temperature) => setEdit({ ...edit, temperature })} suffix="°C"/><label className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs font-semibold">Acara khusus<input type="checkbox" checked={edit.event} onChange={(event) => setEdit({ ...edit, event: event.target.checked })} className="accent-emerald-700"/></label><Field label="Alasan perubahan" value={edit.reason} onChange={(reason) => setEdit({ ...edit, reason })} placeholder={`Penyesuaian rencana ${day ? weekday(day.prediction_date) : ''}`}/></div><button disabled={busy || !canEdit} onClick={saveDay} className="mt-5 w-full rounded-xl bg-[#173d32] py-3 text-xs font-bold text-white disabled:opacity-60">{busy ? 'Menyimpan...' : 'Simpan Perubahan'}</button></>}</article></div>
    <div className="mt-4 grid grid-cols-3 gap-4">{[['Total limbah', `${kg(totalWaste, 0)} kg`], ['Perkiraan biaya', rupiah(totalCost)], ['Potensi hemat', rupiah(excess)]].map((x) => <article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-xl text-[#173d32]">{x[1]}</strong></article>)}</div>
    <p className="mt-3 text-[10px] text-slate-400">{plan.title} · versi model sama untuk ketujuh hari · rencana tidak mengubah Input Data Harian.</p>
    </>}
  </div>
}
