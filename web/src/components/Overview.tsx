'use client'

import { useEffect, useState } from 'react'
import {
  allOperations, applyScenario, createScenario, getDashboard, getInsights, getReportSummary, getScenarioOptions,
  getTrend, listScenarios, predictOperation,
  type Dashboard, type DailyOperation, type ReportSummary, type Scenario, type ScenarioOptions, type Trend,
} from '@/lib/api'
import {
  addDays, average, categoryShares, clockTime, daysBetween, kg, longDate, monthEnd, monthName, monthStart, num,
  percent, riskLabel, rupiah, shortRupiah, weekdayAverages, withActual, actual,
} from '@/lib/format'
import { useApp } from './context'
import { Donut, Icon, TrendChart, type IconName } from './ui'

type Data = {
  dashboard: Dashboard | null
  trend: Trend | null
  operations: DailyOperation[]
  month: ReportSummary | null
  lastMonth: ReportSummary | null
  scenarios: Scenario[]
  composition: ReturnType<typeof categoryShares>
  options: ScenarioOptions | null
  loadedAt: string
}

const value = <T,>(result: PromiseSettledResult<T>, fallback: T) => (result.status === 'fulfilled' ? result.value : fallback)

/** Opsi pengurangan dengan hemat terbesar, maksimal 10% agar cadangan porsi tetap ada. */
export function bestOption(options: ScenarioOptions | null) {
  return options?.options
    .filter((item) => item.reduction_percent > 0 && item.reduction_percent <= 10 && Number(item.savings_kg) > 0)
    .sort((a, b) => Number(b.savings_kg) - Number(a.savings_kg))[0] ?? null
}

export default function Overview() {
  const { today, version, settings, navigate, openDetail, fail, refresh, canEdit } = useApp()
  const [data, setData] = useState<Data | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    const lastMonthDay = addDays(monthStart(today), -1)
    Promise.allSettled([
      getDashboard(today),
      getTrend(today, 30),
      allOperations(addDays(today, -59), today),
      getReportSummary(monthStart(today), today),
      getReportSummary(monthStart(lastMonthDay), monthEnd(lastMonthDay)),
      listScenarios(),
      getInsights(addDays(today, -29), today),
    ]).then(async ([dashboard, trend, operations, month, lastMonth, scenarios, insights]) => {
      const dash = value(dashboard, null)
      let options: ScenarioOptions | null = null
      if (dash?.operation) options = await getScenarioOptions(dash.operation.id, null).catch(() => null)
      if (!alive) return
      if (dashboard.status === 'rejected') fail('Overview belum dapat dimuat', dashboard.reason)
      setData({
        dashboard: dash,
        trend: value(trend, null),
        operations: value(operations, []),
        month: value(month, null),
        lastMonth: value(lastMonth, null),
        scenarios: value(scenarios, []),
        composition: categoryShares(value(insights, { categories: [], staff_load: [] }).categories),
        options,
        loadedAt: new Date().toISOString(),
      })
    })
    return () => { alive = false }
  }, [today, version, fail])

  const operation = data?.dashboard?.operation ?? null
  const prediction = data?.dashboard?.prediction ?? null
  const stale = Boolean(data?.dashboard?.prediction_is_stale)
  const best = bestOption(data?.options ?? null)
  const appliedToday = data?.dashboard?.applied_scenarios ?? []
  const operations = data?.operations ?? []
  const inRange = (start: string, end: string) => withActual(operations).filter((row) => row.operation_date >= start && row.operation_date <= end).map((row) => actual(row) as number)

  async function runPrediction() {
    if (!operation) return
    setBusy(true)
    try {
      const result = await predictOperation(operation.id)
      openDetail('Prediksi diperbarui', `Perkiraan limbah hari ini ${kg(result.predicted_waste_kg)} kg (rentang ${kg(result.interval_lower_kg)}–${kg(result.interval_upper_kg)} kg), risiko ${riskLabel[result.risk_level]}.`)
      refresh()
    } catch (error) {
      fail('Prediksi gagal dijalankan', error)
    } finally {
      setBusy(false)
    }
  }

  async function applyBest() {
    if (!operation || !best || !data?.options) return
    setBusy(true)
    try {
      const scenario = await createScenario({ daily_operation_id: operation.id, reduction_percent: best.reduction_percent, kitchen_staff: null, application_date: operation.operation_date, notes: 'Saran paling berdampak dari Overview', status: 'saved' })
      const result = await applyScenario(scenario.id, data.options.operation_version)
      openDetail('Rencana diterapkan', `Jumlah persiapan diubah dari ${scenario.baseline_portions} menjadi ${scenario.simulated_portions} porsi. Prediksi baru ${kg(result.prediction?.predicted_waste_kg ?? scenario.predicted_waste_kg)} kg.`)
      refresh()
    } catch (error) {
      fail('Saran belum dapat diterapkan', error)
    } finally {
      setBusy(false)
    }
  }

  // ---------- Kartu hero ----------
  const risk = prediction && !stale ? riskLabel[prediction.risk_level] : null
  const tone = risk === 'Tinggi' ? { ring: '#f87171', text: 'text-red-300' } : risk === 'Aman' ? { ring: '#6ee7b7', text: 'text-emerald-300' } : { ring: '#f4b844', text: 'text-amber-300' }
  const ringPercent = prediction && settings ? Math.max(6, Math.min(100, (Number(prediction.predicted_waste_kg) / (Number(settings.warning_max_kg) * 1.25)) * 100)) : 0
  const chips = operation ? [
    operation.special_event ? `Acara khusus${operation.event_type ? `: ${operation.event_type}` : ''}` : 'Tanpa acara khusus',
    `Staf ${operation.staff_experience === 'expert' ? 'ahli' : operation.staff_experience === 'beginner' ? 'pemula' : 'menengah'}`,
    `${Math.round(operation.meals_prepared / operation.kitchen_staff)} porsi/staf`,
  ] : []
  const mae = num(data?.dashboard?.model?.test_mae)

  // ---------- Pola mingguan ----------
  const busiest = weekdayAverages(operations.filter((row) => row.operation_date >= addDays(today, -29)))[0]

  // ---------- Empat metrik ----------
  const last7 = average(inRange(addDays(today, -6), today))
  const prev7 = average(inRange(addDays(today, -13), addDays(today, -7)))
  const weekChange = last7 !== null && prev7 ? ((last7 - prev7) / prev7) * 100 : null
  const monthCost = num(data?.month?.estimated_actual_waste_cost) ?? 0
  const perDay = (summary: ReportSummary | null | undefined) => summary && summary.actual_recorded_count ? (num(summary.estimated_actual_waste_cost) ?? 0) / summary.actual_recorded_count : null
  const costChange = perDay(data?.month) !== null && perDay(data?.lastMonth) !== null ? (perDay(data?.month) as number) - (perDay(data?.lastMonth) as number) : null
  const appliedMonth = (data?.scenarios ?? []).filter((item) => item.status === 'applied' && item.application_date >= monthStart(today) && item.application_date <= today)
  const savedKg = appliedMonth.reduce((sum, item) => sum + Number(item.savings_kg), 0)
  const savedAmount = appliedMonth.reduce((sum, item) => sum + Number(item.savings_amount), 0)
  const warning = Number(settings?.warning_max_kg ?? Infinity)
  const highNow = inRange(addDays(today, -29), today).filter((v) => v > warning).length
  const highBefore = inRange(addDays(today, -59), addDays(today, -30)).filter((v) => v > warning).length
  const cost = shortRupiah(monthCost)
  const metrics = [
    { label: 'Rata-rata 7 Hari', value: last7 === null ? '-' : kg(last7), unit: 'kg/hari', icon: 'leaf', note: weekChange === null ? 'Belum ada pembanding minggu lalu' : `${weekChange <= 0 ? '↓' : '↑'} ${percent(Math.abs(weekChange))} dari minggu lalu`, tone: 'green' },
    { label: 'Biaya Limbah Bulan Ini', value: cost.value, unit: cost.unit, icon: 'database', note: costChange === null ? `${data?.month?.actual_recorded_count ?? 0} hari tercatat` : Math.round(costChange) === 0 ? 'Sama dengan rata-rata harian bulan lalu' : `${costChange < 0 ? '↓' : '↑'} ${rupiah(Math.abs(costChange))}/hari dari bulan lalu`, tone: 'lime' },
    { label: 'Berhasil Dihemat', value: kg(savedKg, savedKg % 1 ? 1 : 0), unit: 'kg', icon: 'spark', note: appliedMonth.length ? `Senilai ${rupiah(savedAmount)} dari ${appliedMonth.length} simulasi` : 'Belum ada simulasi diterapkan bulan ini', tone: 'blue' },
    { label: 'Hari Risiko Tinggi', value: String(highNow), unit: 'hari', icon: 'alert', note: highNow === highBefore ? 'Sama dengan 30 hari sebelumnya' : `${Math.abs(highNow - highBefore)} hari lebih ${highNow < highBefore ? 'sedikit' : 'banyak'}`, tone: 'orange' },
  ]

  // ---------- Rekomendasi ----------
  const load = operation ? operation.meals_prepared / operation.kitchen_staff : null
  const neededStaff = operation ? Math.ceil(operation.meals_prepared / 35) : 0
  const topCategory = data?.composition.items[0]
  const recommendations: Array<{ title: string; desc: string; tone: string; icon: IconName; body: string; go?: 'Input Data Harian' | 'Simulasi Porsi' | 'Insight & Penyebab' }> = [
    !operation
      ? { title: 'Isi rencana hari ini', desc: 'Rekomendasi porsi muncul setelah rencana hari ini disimpan.', tone: 'green', icon: 'trend', body: 'Buka Input Data Harian, isi kondisi dapur hari ini, lalu tekan Simpan & Prediksi.', go: 'Input Data Harian' }
      : best
        ? { title: `Kurangi ${best.reduction_percent}% porsi`, desc: `Siapkan ${best.simulated_portions} dari rencana ${data?.options?.baseline_portions} porsi.`, tone: 'green', icon: 'trend', body: `Model memperkirakan limbah turun dari ${kg(data?.options?.baseline_waste_kg)} kg menjadi ${kg(best.predicted_waste_kg)} kg, hemat ${kg(best.savings_kg)} kg atau ${rupiah(best.savings_amount)}. Bandingkan pilihan lain di Simulasi Porsi.`, go: 'Simulasi Porsi' }
        : { title: 'Porsi sudah efisien', desc: 'Pengurangan 5–10% tidak menurunkan perkiraan limbah.', tone: 'green', icon: 'trend', body: 'Untuk rencana hari ini, model tidak memperkirakan penurunan limbah dari pengurangan porsi 5–10%. Pertahankan rencana atau periksa kondisi lain.', go: 'Simulasi Porsi' },
    load === null
      ? { title: 'Pantau beban staf', desc: 'Jaga beban di bawah 35 porsi per staf.', tone: 'lime', icon: 'leaf', body: 'Beban staf dihitung dari jumlah porsi dibagi jumlah staf dapur pada rencana harian.' }
      : load > 35
        ? { title: `Tambah ${neededStaff - (operation?.kitchen_staff ?? 0)} staf`, desc: `Beban ${Math.round(load)} porsi/staf; idealnya ≤35.`, tone: 'lime', icon: 'leaf', body: `Dengan ${operation?.meals_prepared} porsi, ${neededStaff} staf membuat beban turun ke ${Math.round((operation?.meals_prepared ?? 0) / neededStaff)} porsi per staf.` }
        : { title: 'Beban staf aman', desc: `${Math.round(load)} porsi per staf hari ini.`, tone: 'lime', icon: 'leaf', body: `${operation?.kitchen_staff} staf menangani ${operation?.meals_prepared} porsi. Beban masih di bawah batas 35 porsi per staf.` },
    topCategory
      ? { title: `Prioritaskan ${topCategory.label.toLowerCase()}`, desc: `${topCategory.value}% limbah 30 hari terakhir.`, tone: 'orange', icon: 'alert', body: `${topCategory.label} menyumbang ${kg(topCategory.kg)} kg (${topCategory.value}%) dari limbah aktual 30 hari terakhir. Periksa pembelian, penyimpanan, dan porsi bahan ini lebih dulu.`, go: 'Insight & Penyebab' }
      : { title: 'Catat kategori limbah', desc: 'Isi kategori saat mencatat limbah aktual.', tone: 'orange', icon: 'alert', body: 'Komposisi limbah dihitung dari kategori dan limbah aktual yang dicatat di Input Data Harian.', go: 'Input Data Harian' },
  ]

  // ---------- Target pengurangan ----------
  const target = Number(settings?.reduction_target_percent ?? data?.dashboard?.reduction_target_percent ?? 0)
  const avgThis = num(data?.month?.average_actual_waste_kg)
  const avgLast = num(data?.lastMonth?.average_actual_waste_kg)
  const reduction = avgThis !== null && avgLast ? ((avgLast - avgThis) / avgLast) * 100 : null
  const progress = reduction !== null && target > 0 ? Math.max(0, Math.min(100, (reduction / target) * 100)) : 0
  const daysLeft = daysBetween(today, monthEnd(today))

  return <>
    <section className="mb-4 grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
      <article className="card overflow-hidden bg-[#173d32] text-white"><div className="grid items-center gap-5 sm:grid-cols-[180px_1fr]"><div className="dashboard-risk-ring relative mx-auto grid h-40 w-40 place-items-center rounded-full" style={{ background: `conic-gradient(${tone.ring} 0 ${ringPercent}%, #ffffff18 ${ringPercent}%)` }}><div className="grid h-28 w-28 place-items-center rounded-full bg-[#173d32] text-center"><div><Icon name={risk === 'Aman' ? 'check' : 'alert'} className={`mx-auto ${risk ? tone.text : 'text-white/40'}`}/><strong className={`mt-1 block text-lg ${risk ? tone.text : 'text-white/60'}`}>{risk ?? (data ? 'Belum ada' : '...')}</strong><span className="text-[10px] text-white/50">Risiko hari ini</span></div></div></div><div>
        <p className="text-sm text-white/55">Prediksi limbah hari ini</p>
        {prediction && !stale ? <>
          <h2 className="mt-2 text-4xl font-bold">{kg(prediction.predicted_waste_kg)} kg</h2>
          <p className="mt-2 text-sm text-white/55">Rentang {kg(prediction.interval_lower_kg)}–{kg(prediction.interval_upper_kg)} kg{mae !== null ? ` · biasanya meleset ±${kg(mae)} kg` : ''}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-[10px]">{chips.map((chip) => <span key={chip} className="rounded-full bg-white/10 px-3 py-1.5">{chip}</span>)}{prediction.outside_training_range && <span className="rounded-full bg-orange-400/20 px-3 py-1.5 text-orange-200">Di luar rentang data latih</span>}</div>
        </> : operation ? <>
          <h2 className="mt-2 text-3xl font-bold">{stale ? 'Prediksi perlu diperbarui' : 'Prediksi belum dijalankan'}</h2>
          <p className="mt-2 text-sm text-white/55">{stale ? 'Rencana hari ini berubah setelah prediksi terakhir.' : `Rencana ${operation.meals_prepared} porsi sudah tersimpan.`}</p>
          <div className="mt-4 flex flex-wrap gap-2 text-[10px]">{canEdit && <button disabled={busy} onClick={runPrediction} className="rounded-full bg-[#c7ef5d] px-4 py-2 text-xs font-bold text-[#173d32] disabled:opacity-60">{busy ? 'Memproses...' : 'Jalankan prediksi'}</button>}{chips.map((chip) => <span key={chip} className="rounded-full bg-white/10 px-3 py-1.5">{chip}</span>)}</div>
        </> : <>
          <h2 className="mt-2 text-3xl font-bold">{data ? 'Belum ada rencana' : 'Memuat...'}</h2>
          <p className="mt-2 text-sm text-white/55">Simpan rencana operasional hari ini untuk melihat prediksi limbah.</p>
          <div className="mt-4 flex flex-wrap gap-2 text-[10px]"><button onClick={() => navigate('Input Data Harian', today)} className="rounded-full bg-white/10 px-4 py-2 text-xs font-semibold hover:bg-white/15">Isi Input Data Harian</button></div>
        </>}
      </div></div></article>
      <article className="card border-l-4 border-l-emerald-500"><span className="metric-icon green"><Icon name="leaf"/></span><p className="mt-4 text-sm font-semibold">Saran paling berdampak</p>
        {appliedToday.length ? <>
          <h3 className="mt-2 text-2xl font-bold text-[#173d32]">Saran sudah diterapkan</h3>
          <p className="mt-2 text-sm text-slate-500">Rencana hari ini memakai {appliedToday[0].simulated_portions} porsi, hemat sekitar <strong>{kg(appliedToday[0].savings_kg)} kg / {rupiah(appliedToday[0].savings_amount)}</strong>.</p>
          <button onClick={() => navigate('Simulasi Porsi')} className="mt-5 w-full rounded-xl bg-emerald-100 py-3 text-xs font-bold text-emerald-800">Lihat Simulasi Porsi</button>
        </> : best && operation ? <>
          <h3 className="mt-2 text-2xl font-bold text-[#173d32]">Kurangi {(data?.options?.baseline_portions ?? 0) - best.simulated_portions} porsi</h3>
          <p className="mt-2 text-sm text-slate-500">Hemat sekitar <strong>{kg(best.savings_kg)} kg / {rupiah(best.savings_amount)}</strong> hari ini menurut model aktif ({best.reduction_percent}% dari rencana).</p>
          <button disabled={busy || !canEdit} onClick={applyBest} className="mt-5 w-full rounded-xl bg-emerald-100 py-3 text-xs font-bold text-emerald-800 disabled:opacity-60">{busy ? 'Memproses...' : 'Terapkan Saran'}</button>
        </> : <>
          <h3 className="mt-2 text-2xl font-bold text-[#173d32]">{operation ? 'Rencana sudah efisien' : 'Belum ada saran'}</h3>
          <p className="mt-2 text-sm text-slate-500">{operation ? 'Pengurangan porsi 5–10% tidak menurunkan perkiraan limbah hari ini.' : 'Saran porsi dihitung dari rencana hari ini yang tersimpan.'}</p>
          <button onClick={() => navigate(operation ? 'Simulasi Porsi' : 'Input Data Harian', today)} className="mt-5 w-full rounded-xl bg-emerald-100 py-3 text-xs font-bold text-emerald-800">{operation ? 'Buka Simulasi Porsi' : 'Buka Input Data Harian'}</button>
        </>}
      </article>
    </section>
    <section className="mb-7">
      <div><p className="mb-1 text-sm font-medium text-[#2d826b]">{longDate(today)}</p><h1 className="text-2xl font-bold tracking-tight sm:text-[30px]">{busiest ? `${busiest.day} paling boros: rata-rata ${kg(busiest.average)} kg` : 'Belum ada limbah aktual 30 hari terakhir'}</h1><p className="mt-1 text-sm text-slate-500">{busiest ? `Fokus minggu ini: kurangi persiapan berlebih pada hari ${busiest.day}.` : 'Catat limbah aktual setelah penimbangan agar pola harian terlihat.'}</p></div>
    </section>

    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {metrics.map((m) => <article key={m.label} className="card group min-h-[158px]">
        <div className="flex items-start justify-between"><p className="text-sm font-medium text-slate-500">{m.label}</p><span className={`metric-icon ${m.tone}`}><Icon name={m.icon as IconName} size={19}/></span></div>
        <div className="mt-5 flex items-baseline gap-1.5"><strong className={`text-[28px] font-bold tracking-tight ${m.tone === 'orange' ? 'text-[#b75f24]' : 'text-[#173d32]'}`}>{data ? m.value : '...'}</strong><span className="text-xs font-medium text-slate-400">{m.unit}</span></div>
        <p className={`mt-2 text-xs ${m.tone === 'orange' ? 'text-orange-600' : m.tone === 'lime' ? 'text-emerald-600' : 'text-slate-400'}`}>{data ? m.note : 'Memuat...'}</p>
      </article>)}
    </section>

    <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.8fr)_minmax(320px,.8fr)]">
      <article className="card">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="section-title">Perbandingan Aktual vs Prediksi</h2><p className="section-subtitle">30 hari terakhir · sumbu dalam kilogram</p></div><span className="rounded-lg bg-[#f2f4f1] px-3 py-2 text-[11px] font-semibold text-[#1f5b4c]">30 Hari</span></div>
        <TrendChart series={data?.trend?.series ?? []} startsOn={data?.trend?.starts_on ?? addDays(today, -29)} endsOn={data?.trend?.ends_on ?? today} settings={settings} mae={num(data?.trend?.mae_kg)}/>
      </article>
      <article className="card flex flex-col">
        <h2 className="section-title">Komposisi Waste</h2><p className="section-subtitle">Proporsi limbah aktual 30 hari terakhir per kategori</p>
        <div className="flex flex-1 flex-col items-center justify-center gap-4 py-4 sm:flex-row xl:flex-col 2xl:flex-row"><Donut composition={data?.composition.items ?? []}/><div className="w-full space-y-3">
          {(data?.composition.items ?? []).map(({ label, value, color }) => <div key={label} className="flex items-center text-xs"><i className="mr-2.5 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }}/><span className="text-slate-500">{label}</span><strong className="ml-auto text-slate-700">{value}%</strong></div>)}
          {data && !data.composition.items.length && <p className="text-center text-xs text-slate-400">Belum ada limbah aktual berkategori.</p>}
        </div></div>
      </article>
    </section>

    <section className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
      <article className="card">
        <div className="flex items-start justify-between"><div><h2 className="section-title">Rekomendasi Hari Ini</h2><p className="section-subtitle">Saran dari prediksi model dan catatan restoran</p></div><span className="rounded-full bg-[#edf7d5] px-3 py-1 text-[10px] font-bold text-[#54752b]">{recommendations.length} SARAN</span></div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {recommendations.map((item) => <button onClick={() => openDetail(item.title, item.body)} key={item.title} className="group rounded-xl border border-slate-100 bg-[#fafbf9] p-4 text-left transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-sm"><span className={`mb-4 grid h-8 w-8 place-items-center rounded-lg ${item.tone === 'green' ? 'bg-emerald-100 text-emerald-700' : item.tone === 'lime' ? 'bg-lime-100 text-lime-700' : 'bg-orange-100 text-orange-700'}`}><Icon name={item.icon} size={16}/></span><p className="text-sm font-semibold">{item.title}</p><p className="mt-1.5 text-[11px] leading-5 text-slate-400">{item.desc}</p><span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-[#2d826b]">Lihat detail <Icon name="arrow" size={13}/></span></button>)}
        </div>
      </article>
      <article className="card">
        <div className="flex items-start justify-between"><div><h2 className="section-title">Target Pengurangan</h2><p className="section-subtitle">Rata-rata limbah harian {monthName(today)} dibanding bulan lalu</p></div><span className="text-xs font-semibold text-[#2d826b]">{daysLeft} hari lagi</span></div>
        <div className="mt-7 flex items-end justify-between"><div><strong className="text-3xl font-bold text-[#173d32]">{percent(progress)}</strong><p className="mt-1 text-xs text-slate-400">dari target bulanan</p></div><p className="text-right text-xs leading-5 text-slate-500"><strong className="text-slate-700">{reduction === null ? '-' : `${reduction >= 0 ? 'Turun' : 'Naik'} ${percent(Math.abs(reduction), 1)}`}</strong> per hari<br/>Target turun {percent(target, 1)}</p></div>
        <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-slate-100"><div className="progress-bar h-full rounded-full bg-gradient-to-r from-[#2d826b] to-[#b9d85d]" style={{ width: `${progress}%` }}/></div>
        <div className="mt-5 flex items-center gap-2 rounded-xl bg-[#f3f8e8] px-4 py-3 text-xs text-[#4d6a2c]"><Icon name="trend" size={16}/><span>{reduction === null ? `Rata-rata bulan ini ${kg(avgThis)} kg/hari. Belum ada data bulan lalu sebagai pembanding.` : reduction >= target ? <><strong>Bagus!</strong> Target pengurangan bulan ini tercapai.</> : reduction > 0 ? <><strong>Hampir!</strong> Rata-rata harian {percent(reduction, 1)} lebih rendah dari bulan lalu.</> : <>Rata-rata harian {percent(Math.abs(reduction), 1)} lebih tinggi dari bulan lalu.</>}</span></div>
      </article>
    </section>
    <p className="pb-2 pt-7 text-center text-[10px] text-slate-400">{data ? `Data dari FastAPI • Diperbarui pukul ${clockTime(data.loadedAt)}` : 'Memuat data dari FastAPI...'}{data?.dashboard?.model ? ` • Model ${data.dashboard.model.version_key}` : ''}</p>
  </>
}

