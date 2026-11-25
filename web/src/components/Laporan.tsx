'use client'

import { useEffect, useState } from 'react'
import {
  allOperations, createReport, getReportSummary, getTrend, listScenarios, reportFileUrl,
  type DailyOperation, type ReportSummary, type Scenario, type Trend,
} from '@/lib/api'
import {
  CATEGORIES, actual, addDays, average, categoryLabel, categoryShares, daysBetween, experienceAverages, factorDifferences,
  kg, mediumDate, monthEnd, monthName, monthStart, num, percent, rangeLabel, riskOf, rupiah, weekdayAverages, withActual,
} from '@/lib/format'
import { useApp } from './context'
import { Empty, Field, Icon, TrendChart, selectClass } from './ui'

type Range = 'Mingguan' | 'Bulanan' | 'Kustom'
type Data = { summary: ReportSummary; previous: ReportSummary; rows: DailyOperation[]; trend: Trend; scenarios: Scenario[] }

export default function Laporan() {
  const { today, version, settings, user, openDetail, fail } = useApp()
  const [reportRange, setReportRange] = useState<Range>('Bulanan')
  const [customStart, setCustomStart] = useState(monthStart(today))
  const [customEnd, setCustomEnd] = useState(today)
  const [category, setCategory] = useState('')
  const [search, setSearch] = useState('')
  const [data, setData] = useState<Data | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [exportType, setExportType] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [mail, setMail] = useState({ recipient: '', subject: '', message: '', format: 'pdf' as 'pdf' | 'xlsx' })

  const [start, end] = reportRange === 'Mingguan' ? [addDays(today, -6), today] : reportRange === 'Bulanan' ? [monthStart(today), monthEnd(today)] : [customStart, customEnd]
  const span = daysBetween(start, end) + 1
  const invalid = !start || !end || end < start ? 'Tanggal akhir tidak boleh sebelum tanggal mulai.' : span > 366 ? 'Maksimal satu tahun per laporan.' : null
  const periodName = reportRange === 'Bulanan' ? monthName(today) : reportRange === 'Mingguan' ? '7 hari terakhir' : rangeLabel(start, end)
  const categoryName = category ? categoryLabel(category) : 'Semua kategori'

  useEffect(() => {
    if (invalid) { setError(invalid); return }
    let alive = true
    setError(null)
    Promise.all([
      getReportSummary(start, end, category || null),
      getReportSummary(addDays(start, -span), addDays(start, -1), category || null),
      allOperations(start, end, category || null),
      getTrend(end, Math.min(180, Math.max(7, span))),
      listScenarios(),
    ]).then(([summary, previous, rows, trend, scenarios]) => alive && setData({ summary, previous, rows, trend, scenarios }))
      .catch((reason) => { if (alive) { setData(null); fail('Laporan belum dapat dimuat', reason) } })
    return () => { alive = false }
  }, [start, end, span, category, invalid, version, fail])

  const rows = data?.rows ?? []
  const total = num(data?.summary.total_actual_waste_kg)
  const cost = num(data?.summary.estimated_actual_waste_cost)
  const avgNow = num(data?.summary.average_actual_waste_kg)
  const avgBefore = num(data?.previous.average_actual_waste_kg)
  const change = avgNow !== null && avgBefore ? ((avgNow - avgBefore) / avgBefore) * 100 : null
  const applied = (data?.scenarios ?? []).filter((item) => item.status === 'applied' && item.application_date >= start && item.application_date <= end)
  const savedKg = applied.reduce((sum, item) => sum + Number(item.savings_kg), 0)
  const savedByOperation = new Map(applied.map((item) => [item.daily_operation_id, Number(item.savings_amount)]))
  const weekdays = weekdayAverages(rows)
  const bestDay = weekdays[weekdays.length - 1]
  const worstDay = weekdays[0]
  const overall = average(withActual(rows).map((row) => actual(row) as number))
  const factors = factorDifferences(rows).filter((item) => item.impact > 0)
  const experience = experienceAverages(rows).filter((item) => item.average !== null).sort((a, b) => (a.average as number) - (b.average as number))
  const shares = categoryShares(data?.summary.by_category ?? [])
  const findings = [
    worstDay && overall !== null && worstDay.average > overall ? `${worstDay.day} rata-rata ${kg(worstDay.average - overall)} kg lebih boros.` : null,
    factors[0] ? `${factors[0].label} menambah sekitar ${kg(factors[0].impact)} kg.` : null,
    experience.length > 1 ? `Staf ${experience[0].label.toLowerCase()} menghemat sekitar ${kg((experience[experience.length - 1].average as number) - (experience[0].average as number))} kg per hari.` : null,
    shares.items[0] ? `${shares.items[0].label} menyumbang ${shares.items[0].value}% dari total limbah.` : null,
    num(data?.summary.prediction_mae_kg) !== null ? `Prediksi meleset rata-rata ±${kg(data?.summary.prediction_mae_kg)} kg dari ${data?.summary.prediction_pairs} pasangan.` : null,
  ].filter((item): item is string => Boolean(item))
  const recommendations = [
    worstDay ? `Turunkan persiapan ${worstDay.day} sekitar 5–10% lalu bandingkan di Simulasi Porsi.` : null,
    factors.some((item) => item.label === 'Beban staf berat') ? 'Jaga beban staf di bawah 35 porsi per staf.' : experience.length > 1 ? `Tambah satu staf ${experience[0].label.toLowerCase()} pada hari ramai.` : null,
    shares.items[0] ? `Batasi pembelian ${shares.items[0].label.toLowerCase()} (limbah ${kg((shares.items[0].kg / Math.max(1, span)) * 7)} kg per minggu).` : null,
  ].filter((item): item is string => Boolean(item))
  const filtered = rows.filter((row) => {
    const text = [mediumDate(row.operation_date), categoryLabel(row.waste_category), riskOf(num(row.actual_waste_kg), settings) ?? 'belum ditimbang', row.manager_notes ?? ''].join(' ').toLowerCase()
    return text.includes(search.toLowerCase())
  }).reverse()
  const filterText = `${reportRange} · ${categoryName} · ${rangeLabel(start, end)}`

  function openExport(type: string) {
    setMail({
      recipient: settings?.report_recipient_email ?? user.email,
      subject: `Laporan ${reportRange} FoodSave — ${rangeLabel(start, end)}`,
      message: `Halo, berikut laporan ${reportRange.toLowerCase()} ${user.restaurantName}. Total limbah ${kg(total)} kg dengan perkiraan biaya ${rupiah(cost)}. Mohon tinjau rincian harian terlampir.`,
      format: 'pdf',
    })
    setExportType(type)
  }

  async function finishExport() {
    if (invalid || !exportType) return
    setBusy(true)
    try {
      const email = exportType === 'Kirim ke Email'
      const report = await createReport({
        starts_on: start,
        ends_on: end,
        period_type: reportRange === 'Mingguan' ? 'weekly' : reportRange === 'Bulanan' ? 'monthly' : 'custom',
        waste_category: category || null,
        search: null,
        sort_order: 'date_asc',
        file_format: email ? mail.format : exportType === 'Unduh PDF' ? 'pdf' : 'xlsx',
        email_recipient: email ? mail.recipient.trim() : null,
        email_subject: email ? mail.subject.trim() : null,
        email_message: email ? mail.message.trim() : null,
      })
      setExportType(null)
      if (report.generation_status !== 'ready') {
        openDetail('Laporan gagal dibuat', 'Backend gagal membuat file laporan. Periksa log layanan api lalu coba lagi.')
      } else if (email) {
        openDetail(report.email_status === 'pending' ? 'Email masuk antrean' : 'Email belum dikirim', report.email_status === 'pending'
          ? `Laporan ${report.file_name} akan dikirim ke ${report.email_recipient} oleh pekerja laporan dalam beberapa detik. Di laptop ini email ditangkap Mailpit: buka http://localhost:8026 untuk melihatnya.`
          : 'File laporan sudah dibuat, tetapi layanan email backend belum aktif (MAIL_BACKEND). File tetap bisa diunduh lewat tombol Unduh.')
      } else {
        const link = document.createElement('a')
        link.href = reportFileUrl(report.id)
        link.download = report.file_name ?? ''
        document.body.appendChild(link)
        link.click()
        link.remove()
        openDetail('Laporan dibuat', `${report.file_name} dibuat oleh backend dan sedang diunduh. Filter: ${filterText}.`)
      }
    } catch (reason) {
      fail('Laporan belum dapat dibuat', reason)
    } finally {
      setBusy(false)
    }
  }

  return <div className="page-enter">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-bold sm:text-[30px]">{!data ? 'Memuat laporan...' : change !== null ? `Limbah ${change <= 0 ? 'turun' : 'naik'} ${percent(Math.abs(change))}: biaya ${rupiah(cost)}` : total !== null ? `Total limbah ${kg(total)} kg: biaya ${rupiah(cost)}` : 'Belum ada limbah aktual pada periode ini'}</h1><p className="mt-1 text-sm text-slate-500">Ringkasan {reportRange.toLowerCase()} · {categoryName.toLowerCase()} · {rangeLabel(start, end)}.</p></div><div className="flex gap-2">{['Unduh PDF', 'Unduh Excel', 'Kirim ke Email'].map((x) => <button disabled={Boolean(invalid)} onClick={() => openExport(x)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold disabled:opacity-50" key={x}>{x}</button>)}</div></div>
    <div className="mb-4 flex flex-wrap gap-2">{(['Mingguan', 'Bulanan', 'Kustom'] as Range[]).map((x) => <button onClick={() => setReportRange(x)} className={`rounded-full px-4 py-2 text-xs font-semibold ${reportRange === x ? 'bg-[#173d32] text-white' : 'bg-white'}`} key={x}>{x}</button>)}<select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-full border-0 bg-white px-4 text-xs"><option value="">Semua kategori</option>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select>{reportRange === 'Kustom' && <><input type="date" value={customStart} onChange={(e) => e.target.value && setCustomStart(e.target.value)} className="rounded-full border-0 bg-white px-4 text-xs"/><input type="date" value={customEnd} onChange={(e) => e.target.value && setCustomEnd(e.target.value)} className="rounded-full border-0 bg-white px-4 text-xs"/></>}</div>
    {error && <div className="mb-4 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><Icon name="alert"/>{error}</div>}
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{[['Total limbah', total === null ? '-' : `${kg(total)} kg`], ['Total biaya', rupiah(cost)], ['Berhasil dihemat', `${kg(savedKg)} kg`], ['Dibanding lalu', change === null ? '-' : `${change <= 0 ? '↓' : '↑'} ${percent(Math.abs(change))}`], ['Terbaik / Terburuk', weekdays.length > 1 ? `${bestDay.day} / ${worstDay.day}` : '-']].map((x) => <article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-lg text-[#173d32]">{data ? x[1] : '...'}</strong></article>)}</div>
    <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_.8fr]"><article className="card"><h2 className="section-title">Tren Limbah {reportRange === 'Bulanan' ? `Bulan ${monthName(today)}` : periodName}</h2><p className="section-subtitle">Tanggal vs limbah (kg) · {data?.summary.operation_count ?? 0} hari tercatat, {data?.summary.actual_missing_count ?? 0} belum ditimbang</p><TrendChart series={data?.trend.series.filter((item) => item.date >= start && item.date <= end) ?? []} startsOn={data?.trend.starts_on ?? start} endsOn={data?.trend.ends_on ?? end} settings={settings} mae={num(data?.summary.prediction_mae_kg)}/></article><article className="card"><h2 className="section-title">Temuan Utama</h2>{findings.length ? <ol className="mt-5 space-y-3">{findings.map((x, i) => <li className="flex gap-3 text-xs leading-5" key={x}><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-100 font-bold text-emerald-700">{i + 1}</span>{x}</li>)}</ol> : <div className="mt-5"><Empty>Temuan muncul setelah ada limbah aktual pada periode ini.</Empty></div>}<h3 className="mt-6 text-sm font-bold">Rekomendasi Periode Berikutnya</h3>{recommendations.length ? <ul className="mt-3 space-y-2 text-xs text-slate-600">{recommendations.map((x, i) => <li key={x}>{i + 1}. {x}</li>)}</ul> : <p className="mt-3 text-xs text-slate-400">Belum ada rekomendasi.</p>}</article></div>
    <article className="card mt-4"><div className="flex items-center justify-between gap-4"><h2 className="section-title">Rincian Harian</h2><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Cari tanggal, kategori, atau risiko" className="rounded-lg border border-slate-200 px-3 py-2 text-xs"/></div><div className="mt-4 overflow-x-auto">{filtered.length ? <table className="w-full min-w-[720px] text-left text-xs"><thead><tr className="text-slate-400">{['Tanggal', 'Porsi', 'Staf', 'Kategori', 'Limbah', 'Risiko', 'Hemat'].map((x) => <th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{filtered.map((row) => <tr className="border-t border-slate-100" key={row.id}><td className="py-3">{mediumDate(row.operation_date)}</td><td className="py-3">{row.meals_prepared}</td><td className="py-3">{row.kitchen_staff}</td><td className="py-3">{categoryLabel(row.waste_category)}</td><td className="py-3">{row.actual_waste_kg === null ? 'Belum ditimbang' : `${kg(row.actual_waste_kg)} kg`}</td><td className="py-3">{riskOf(num(row.actual_waste_kg), settings) ?? '-'}</td><td className="py-3">{savedByOperation.has(row.id) ? rupiah(savedByOperation.get(row.id)) : '-'}</td></tr>)}</tbody></table> : <Empty>{data ? 'Tidak ada data harian yang cocok dengan filter.' : 'Memuat...'}</Empty>}</div></article>
    {exportType && <div className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/40 p-4" onMouseDown={() => !busy && setExportType(null)}><article onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl"><div className="flex justify-between"><div><p className="text-xs font-semibold text-emerald-700">SIAPKAN LAPORAN</p><h3 className="mt-1 text-xl font-bold">{exportType}</h3></div><button onClick={() => setExportType(null)}><Icon name="close"/></button></div>{exportType === 'Kirim ke Email' ? <div className="mt-6 space-y-4"><Field label="Penerima email" type="email" value={mail.recipient} onChange={(recipient) => setMail({ ...mail, recipient })}/><Field label="Subjek" value={mail.subject} onChange={(subject) => setMail({ ...mail, subject })}/><label className="block"><span className="mb-2 block text-xs font-semibold">Pesan</span><textarea value={mail.message} onChange={(e) => setMail({ ...mail, message: e.target.value })} className="min-h-28 w-full rounded-xl border border-slate-200 p-3 text-sm"/></label><label className="block"><span className="mb-2 block text-xs font-semibold">Lampiran</span><select value={mail.format} onChange={(e) => setMail({ ...mail, format: e.target.value as 'pdf' | 'xlsx' })} className={selectClass}><option value="pdf">PDF</option><option value="xlsx">Excel (.xlsx)</option></select></label><p className="text-xs text-slate-400">Email dikirim oleh pekerja laporan backend. Di laptop ini email ditangkap Mailpit (http://localhost:8026).</p></div> : <div className="mt-6 space-y-4"><div className="rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">File {exportType === 'Unduh PDF' ? 'PDF' : 'Excel (.xlsx)'} dibuat oleh backend dari data tersimpan: ringkasan periode dan rincian harian beserta prediksi terakhir. Filter aktif: <strong>{filterText}</strong>.</div></div>}<button disabled={busy} onClick={finishExport} className="mt-6 w-full rounded-xl bg-[#173d32] py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? 'Membuat laporan...' : exportType === 'Kirim ke Email' ? 'Kirim Email' : exportType === 'Unduh PDF' ? 'Buat & Unduh PDF' : 'Buat & Unduh Excel'}</button></article></div>}
  </div>
}
