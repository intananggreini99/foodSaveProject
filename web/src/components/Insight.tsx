'use client'

import { useEffect, useState } from 'react'
import { allOperations, getInsights, type DailyOperation, type Insights } from '@/lib/api'
import {
  actual, addDays, average, categoryShares, experienceAverages, factorDifferences, kg, mediumDate,
  weekdayAverages, withActual,
} from '@/lib/format'
import { useApp } from './context'
import { Donut, Empty, Icon } from './ui'

export default function Insight() {
  const { today, version, openDetail, fail } = useApp()
  const [rows, setRows] = useState<DailyOperation[] | null>(null)
  const [insights, setInsights] = useState<Insights | null>(null)

  useEffect(() => {
    const start = addDays(today, -89)
    Promise.all([allOperations(start, addDays(today, 14)), getInsights(start, today)])
      .then(([operations, summary]) => { setRows(operations); setInsights(summary) })
      .catch((error) => { setRows([]); fail('Insight belum dapat dimuat', error) })
  }, [today, version, fail])

  const past = (rows ?? []).filter((row) => row.operation_date <= today)
  const recorded = withActual(past)
  const overall = average(recorded.map((row) => actual(row) as number))
  const factors = factorDifferences(past)
  const top = factors.find((item) => item.impact > 0)
  const maxImpact = Math.max(...factors.map((item) => Math.abs(item.impact)), 0.1)
  const busiest = weekdayAverages(past)[0]
  const experience = experienceAverages(past).filter((item) => item.average !== null)
  const sortedExperience = [...experience].sort((a, b) => (a.average as number) - (b.average as number))
  const bestLevel = sortedExperience[0]
  const worstLevel = sortedExperience[sortedExperience.length - 1]
  const shares = categoryShares(insights?.categories ?? [])
  const categoryCount = (insights?.categories ?? []).filter((item) => Number(item.actual_waste_kg) > 0).reduce((sum, item) => sum + item.operation_count, 0)
  const heavy = insights?.staff_load.find((item) => item.group.startsWith('berat'))
  const lighter = insights?.staff_load.filter((item) => !item.group.startsWith('berat') && item.average_actual_waste_kg !== null) ?? []
  const lighterAverage = lighter.length ? lighter.reduce((sum, item) => sum + Number(item.average_actual_waste_kg) * item.actual_recorded_count, 0) / lighter.reduce((sum, item) => sum + item.actual_recorded_count, 0) : null
  const heavyGap = heavy?.average_actual_waste_kg !== null && heavy?.average_actual_waste_kg !== undefined && lighterAverage !== null ? Number(heavy.average_actual_waste_kg) - lighterAverage : null
  const next = (rows ?? []).find((row) => row.operation_date >= today)
  const maxExperience = Math.max(...experience.map((item) => item.average as number), 1)

  const cards: Array<{ title: string; value: string; desc: string; good: boolean; body: string }> = []
  if (busiest && overall !== null) cards.push({ title: `${busiest.day} paling boros`, value: `+${kg(busiest.average - overall)} kg`, desc: `Rata-rata ${kg(busiest.average)} kg dari ${busiest.count} catatan.`, good: false, body: `Limbah hari ${busiest.day} rata-rata ${kg(busiest.average)} kg, ${kg(busiest.average - overall)} kg di atas rata-rata semua hari (${kg(overall)} kg). Kurangi persiapan awal pada hari ${busiest.day} dan cek di Simulasi Porsi.` })
  if (bestLevel && worstLevel && bestLevel !== worstLevel) cards.push({ title: `Staf ${bestLevel.label.toLowerCase()} lebih hemat`, value: `−${kg((worstLevel.average as number) - (bestLevel.average as number))} kg/hari`, desc: `Dibanding hari dengan staf ${worstLevel.label.toLowerCase()}.`, good: true, body: `Hari dengan staf ${bestLevel.label.toLowerCase()} rata-rata ${kg(bestLevel.average)} kg, sedangkan staf ${worstLevel.label.toLowerCase()} ${kg(worstLevel.average)} kg. Pasangkan staf berpengalaman saat porsi ramai.` })
  if (shares.items[0]) cards.push({ title: `${shares.items[0].label} terbesar`, value: `${shares.items[0].value}%`, desc: 'Periksa pembelian dan penyimpanan.', good: false, body: `${shares.items[0].label} menyumbang ${kg(shares.items[0].kg)} kg dari ${kg(shares.total)} kg limbah aktual 90 hari terakhir. Periksa jumlah pembelian, cara penyimpanan, dan porsi bahan ini.` })

  return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">{rows === null ? 'Memuat insight...' : top ? `Penyebab terbesar limbah: ${top.label.toLowerCase()} (+${kg(top.impact)} kg)` : 'Belum cukup data untuk melihat penyebab limbah'}</h1><p className="mt-1 text-sm text-slate-500">Pola dari {recorded.length} hari catatan limbah aktual (90 hari terakhir), bukan kepastian sebab-akibat.</p></div>
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">{cards.length ? cards.map((x) => <article className={`rounded-xl border p-4 ${x.good ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`} key={x.title}><Icon name={x.good ? 'check' : 'alert'} size={17}/><p className="mt-2 text-xs font-semibold">{x.title}</p><strong className="mt-1 block text-lg">{x.value}</strong><p className="mt-1 text-[10px] text-slate-500">{x.desc}</p><button onClick={() => openDetail(x.title, x.body)} className="mt-2 text-[10px] font-bold text-emerald-800">Lihat saran</button></article>) : <div className="sm:col-span-3"><Empty>Insight muncul setelah ada limbah aktual yang dicatat di Input Data Harian.</Empty></div>}</div>
    <div className="grid gap-4 lg:grid-cols-[1.15fr_.85fr]"><article className="card"><h2 className="section-title">Hal yang Paling Memengaruhi Limbah</h2><p className="section-subtitle">Selisih rata-rata limbah aktual (kg) dibanding hari lainnya</p><div className="mt-6 space-y-4">{factors.length ? factors.map((item) => <div key={item.label}><div className="mb-1 flex justify-between text-xs"><span>{item.label} <span className="text-slate-400">· {item.detail}</span></span><strong className={item.impact > 0 ? 'text-red-600' : 'text-emerald-700'}>{item.impact > 0 ? '+' : ''}{kg(item.impact)} kg</strong></div><div className="h-3 rounded-full bg-slate-100"><div className={`h-full rounded-full ${item.impact > 0 ? 'bg-red-400' : 'bg-emerald-500'}`} style={{ width: `${Math.max(3, (Math.abs(item.impact) / maxImpact) * 100)}%` }}/></div></div>) : <Empty>Perbandingan membutuhkan limbah aktual dari hari dengan kondisi berbeda (acara, beban staf, akhir pekan, pengalaman staf).</Empty>}</div></article><article className="card"><h2 className="section-title">Limbah per Kategori</h2><p className="section-subtitle">Proporsi {categoryCount} catatan · {kg(shares.total)} kg</p><div className="mt-5 flex items-center gap-5"><Donut composition={shares.items}/><div className="space-y-3 text-xs">{shares.items.length ? shares.items.map(({ label, value, color }) => <p key={label} className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }}/><strong>{value}%</strong> {label}</p>) : <p className="text-slate-400">Belum ada limbah aktual berkategori.</p>}</div></div></article></div>
    <div className="mt-4"><article className="card"><h2 className="section-title">Staf & Beban Kerja</h2>{experience.length ? <div className="mt-6 flex h-40 items-end justify-around">{experience.map((item) => <div className="flex flex-col items-center gap-2" key={item.level}><strong className="text-xs">{kg(item.average)} kg</strong><div className="chart-bar w-16 rounded-t-lg bg-[#2d826b]" style={{ height: `${((item.average as number) / maxExperience) * 110}px` }}/><span className="text-xs text-slate-500">{item.label}</span></div>)}</div> : <div className="mt-6"><Empty>Belum ada limbah aktual per tingkat pengalaman staf.</Empty></div>}<p className="mt-5 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">{heavyGap === null ? 'Belum ada cukup hari dengan beban lebih dari 35 porsi per staf untuk dibandingkan.' : <>Saat 1 staf menangani lebih dari 35 porsi, limbah rata-rata {heavyGap >= 0 ? 'naik' : 'turun'} sekitar {kg(Math.abs(heavyGap))} kg. {next && next.meals_prepared / next.kitchen_staff > 35 && <strong>Tambah staf pada {mediumDate(next.operation_date)}.</strong>}</>}</p><button onClick={() => openDetail('Saran jumlah staf ideal', next ? `Rencana ${mediumDate(next.operation_date)}: ${next.meals_prepared} porsi dengan ${next.kitchen_staff} staf (${Math.round(next.meals_prepared / next.kitchen_staff)} porsi per staf). Agar beban ≤35 porsi per staf, siapkan minimal ${Math.ceil(next.meals_prepared / 35)} staf.` : 'Belum ada rencana untuk hari ini atau ke depan. Simpan rencana di Input Data Harian untuk mendapatkan saran jumlah staf.')} className="mt-4 text-xs font-bold text-emerald-700">Saran jumlah staf ideal →</button></article></div>
  </div>
}
