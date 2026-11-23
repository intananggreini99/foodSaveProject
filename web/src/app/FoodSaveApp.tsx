'use client'

import { useEffect, useState } from 'react'
import { getDashboard, getOperationalInsights, hasApiUrl } from '@/lib/api'

type IconName =
  | 'grid'
  | 'chart'
  | 'spark'
  | 'database'
  | 'settings'
  | 'bell'
  | 'calendar'
  | 'arrow'
  | 'leaf'
  | 'menu'
  | 'close'
  | 'trend'
  | 'check'
  | 'alert'
  | 'chevron'

const paths: Record<IconName, React.ReactNode> = {
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

function Icon({ name, size = 20, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

const nav = [
  ['grid', 'Overview'],
  ['database', 'Input Data Harian'],
  ['spark', 'Prediksi 7 Hari'],
  ['chart', 'Simulasi Porsi'],
  ['trend', 'Insight & Penyebab'],
  ['calendar', 'Laporan'],
] as const

export type AppUser = {
  id: string
  email: string
  name: string
  restaurantName: string
}

function Sidebar({ open, close, active, onNavigate, onProfile, user }: { open: boolean; close: () => void; active: string; onNavigate: (page: string) => void; onProfile: () => void; user: AppUser }) {
  return <>
    {open && <button aria-label="Tutup menu" onClick={close} className="fixed inset-0 z-40 bg-slate-950/35 backdrop-blur-sm lg:hidden" />}
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col bg-[#12342b] px-4 py-6 text-white transition-transform duration-300 lg:translate-x-0 ${open ? 'translate-x-0' : '-translate-x-full'}`}>
      <div className="mb-9 flex items-center gap-3 px-2">
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-[#c7ef5d] text-[#17352c]"><Icon name="leaf" size={23}/></div>
        <div><div className="text-[19px] font-bold tracking-tight">FoodSave</div><div className="text-[10px] font-medium uppercase tracking-[.2em] text-emerald-100/55">Restaurant</div></div>
        <button onClick={close} className="ml-auto lg:hidden"><Icon name="close"/></button>
      </div>
      <p className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-emerald-100/40">Menu Utama</p>
      <nav className="space-y-1.5">
        {nav.map(([icon, label]) => <button key={label} onClick={() => { onNavigate(label); close() }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${active === label ? 'bg-white/12 font-semibold text-white shadow-inner' : 'text-emerald-50/65 hover:bg-white/7 hover:text-white'}`}><Icon name={icon}/>{label}{active === label && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#c7ef5d]"/>}</button>)}
      </nav>
      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[.06] p-4">
        <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg bg-[#c7ef5d]/15 text-[#c7ef5d]"><Icon name="leaf" size={19}/></div>
        <p className="text-sm font-semibold">Kurangi waste hari ini</p>
        <p className="mt-1 text-xs leading-5 text-emerald-50/55">Setiap kilogram yang diselamatkan membuat dampak.</p>
      </div>
      <button onClick={onProfile} className="mt-4 flex items-center gap-3 border-t border-white/10 px-2 pt-5 text-left">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-[#ebc8a8] text-xs font-bold text-[#513a2d]">{user.name.split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase()}</div>
        <div className="min-w-0"><p className="truncate text-sm font-semibold">{user.name}</p><p className="text-[11px] text-white/45">Restaurant Manager</p></div>
        <Icon name="chevron" size={16} className="ml-auto text-white/35"/>
      </button>
    </aside>
  </>
}

function TrendChart() {
  const actual = [11,12,10,9,13,15,12,11,10,14,18,13,12,9,8,11,13,16,14,12,10,9,12,17,19,15,13,11,10,12]
  const predicted = [10,11,11,10,12,14,13,10,11,13,15,14,11,10,9,12,12,15,13,13,11,10,11,14,17,14,12,12,11,12]
  const [hover, setHover] = useState<number | null>(null)
  const x = (i: number) => 58 + i * (712 / 29)
  const y = (v: number) => 250 - v * 8.5
  const path = (values: number[]) => values.map((v,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const band = predicted.map((v,i)=>`${x(i)},${y(v+1.2)}`).join(' ')+' '+predicted.map((v,i)=>`${x(29-i)},${y(predicted[29-i]-1.2)}`).join(' ')
  return <div className="mt-5 w-full overflow-hidden">
    <div className="mb-2 flex flex-wrap gap-4 text-[10px] text-slate-500"><span className="flex items-center gap-2"><i className="h-0.5 w-5 bg-[#27715f]"/>Aktual</span><span className="flex items-center gap-2"><i className="h-0 w-5 border-t-2 border-dashed border-orange-400"/>Prediksi</span><span className="flex items-center gap-2"><i className="h-2 w-5 bg-slate-200"/>Rentang perkiraan</span></div>
    <svg viewBox="0 0 800 285" className="h-auto min-h-[245px] w-full" role="img" aria-label="Perbandingan aktual dan prediksi limbah 30 hari dalam kilogram">
      <rect x="58" y={y(25)} width="712" height={y(15)-y(25)} fill="#fee2e2" opacity=".55"/><rect x="58" y={y(15)} width="712" height={y(10)-y(15)} fill="#fef3c7" opacity=".7"/><rect x="58" y={y(10)} width="712" height={y(0)-y(10)} fill="#dcfce7" opacity=".55"/>
      {[0,5,10,15,20,25].map(v=><g key={v}><line x1="58" y1={y(v)} x2="770" y2={y(v)} stroke="#dce3df"/><text x="48" y={y(v)+4} textAnchor="end" fontSize="9" fill="#82908a">{v} kg</text></g>)}
      <text x="14" y="145" transform="rotate(-90 14 145)" fontSize="9" fill="#82908a">Limbah (kg)</text>
      <polygon points={band} fill="#94a3b8" opacity=".18"/>
      <path d={path(predicted)} fill="none" stroke="#e99a3d" strokeWidth="2.5" strokeDasharray="7 6"/>
      <path d={path(actual)} fill="none" stroke="#27715f" strokeWidth="3"/>
      {actual.map((v,i)=><circle key={i} cx={x(i)} cy={y(v)} r={hover===i?6:4} fill="white" stroke="#27715f" strokeWidth="2" onMouseEnter={()=>setHover(i)} onMouseLeave={()=>setHover(null)}/>)}
      {[0,4,9,14,19,24,29].map(i=><text key={i} x={x(i)} y="270" textAnchor="middle" fontSize="9" fill="#82908a">{i+1} Mei</text>)}
      <text x="414" y="283" textAnchor="middle" fontSize="9" fill="#82908a">Tanggal</text>
      {[10,23].map(i=><g key={i}><line x1={x(i)} y1={y(actual[i])-5} x2={x(i)} y2={y(actual[i])-28} stroke="#b45309"/><rect x={x(i)-35} y={y(actual[i])-47} width="70" height="20" rx="6" fill="#fff7ed"/><text x={x(i)} y={y(actual[i])-34} textAnchor="middle" fontSize="8" fontWeight="700" fill="#b45309">Selisih {Math.abs(actual[i]-predicted[i])} kg</text></g>)}
      {hover!==null && <g><rect x={Math.min(650,Math.max(65,x(hover)-55))} y="10" width="125" height="57" rx="8" fill="#173d32"/><text x={Math.min(650,Math.max(65,x(hover)-55))+9} y="26" fontSize="8" fill="white">{hover+1} Mei 2025</text><text x={Math.min(650,Math.max(65,x(hover)-55))+9} y="40" fontSize="8" fill="#d1fae5">Aktual {actual[hover]} kg · Prediksi {predicted[hover]} kg</text><text x={Math.min(650,Math.max(65,x(hover)-55))+9} y="54" fontSize="8" fill="#fdba74">Selisih {Math.abs(actual[hover]-predicted[hover])} kg</text></g>}
    </svg>
    <p className="mt-2 text-[11px] text-slate-400">Prediksi rata-rata meleset ±1,2 kg.</p>
  </div>
}

type WasteSlice = { label: string; value: number; color: string }

const wasteComposition: WasteSlice[] = [
  { label: 'Daging', value: 43, color: '#2d826b' },
  { label: 'Sayur', value: 20, color: '#74a58e' },
  { label: 'Susu', value: 19, color: '#a9c77b' },
  { label: 'Biji-bijian', value: 18, color: '#e8ad65' },
]

function Donut({ composition = wasteComposition }: { insight?: boolean; composition?: WasteSlice[] }) {
  const segments = composition.map(({ value, color }) => [value, color] as const)
  let offset = 0
  return <div className="h-40 w-40 shrink-0">
    <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90 drop-shadow-sm" role="img" aria-label="Donat proporsi kategori limbah">
      <circle cx="60" cy="60" r="43" fill="none" stroke="#edf1ee" strokeWidth="18"/>
      {segments.map(([value,color],i)=>{const start=offset; offset += Number(value); return <circle key={i} cx="60" cy="60" r="43" fill="none" stroke={String(color)} strokeWidth="18" strokeDasharray={`${Number(value)*2.701-2} 270.1`} strokeDashoffset={-start*2.701}/>})}
      <circle cx="60" cy="60" r="28" fill="white"/>
      <text x="60" y="58" textAnchor="middle" fill="#173d32" fontSize="12" fontWeight="700" transform="rotate(90 60 60)">100%</text>
      <text x="60" y="70" textAnchor="middle" fill="#94a3b8" fontSize="6" transform="rotate(90 60 60)">total</text>
    </svg>
  </div>
}

const Field = ({ label, value, suffix }: { label: string; value: string; suffix?: string }) => <label className="block"><span className="mb-2 block text-xs font-semibold text-slate-600">{label}</span><div className="flex rounded-xl border border-slate-200 bg-white px-3 py-2.5 focus-within:border-emerald-500"><input defaultValue={value} className="min-w-0 flex-1 bg-transparent text-sm outline-none"/>{suffix && <span className="text-xs text-slate-400">{suffix}</span>}</div></label>

function AnalysisPage({ page, openDetail, applyPlan }: { page: string; openDetail: (title: string, body: string) => void; applyPlan: (portions: number, staff: number, waste: number) => void }) {
  const [portions, setPortions] = useState(500)
  const [staff, setStaff] = useState(14)
  const [inputTab, setInputTab] = useState('manual')
  const [selectedDay, setSelectedDay] = useState(2)
  const [reportRange, setReportRange] = useState('Bulanan')
  const [reportCategory, setReportCategory] = useState('Semua kategori')
  const [exportType, setExportType] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const predicted = Math.max(4, portions * 0.026).toFixed(1)

  if (page === 'Input Data Harian') return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">Rencana 500 porsi hari ini masih aman</h1><p className="mt-1 text-sm text-slate-500">Isi kondisi dapur, lalu lihat perkiraan limbah secara langsung.</p></div>
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">{[['Beban staf','36 porsi/orang','Tambah 1 staf bila porsi naik.'],['Limbah kemarin','14 kg','Kurangi persiapan daging hari ini.'],['Potensi hemat','Rp45.000','Pakai saran 470 porsi.']].map((x,i)=><article className={`rounded-xl border p-4 ${i===0?'border-amber-200 bg-amber-50':'border-emerald-200 bg-emerald-50'}`} key={x[0]}><Icon name={i===0?'alert':'leaf'} size={17}/><p className="mt-2 text-xs font-semibold">{x[0]}</p><strong className="mt-1 block text-lg">{x[1]}</strong><p className="mt-1 text-[10px] text-slate-500">{x[2]}</p></article>)}</div>
    <div className="mb-4 inline-flex rounded-xl bg-slate-200/60 p-1">{[['manual','Input Manual'],['file','Unggah File (CSV/Excel)']].map(([v,l])=><button key={v} onClick={()=>setInputTab(v)} className={`rounded-lg px-4 py-2 text-xs font-semibold ${inputTab===v?'bg-white text-[#173d32] shadow-sm':'text-slate-500'}`}>{l}</button>)}</div>
    {inputTab === 'file' ? <article className="card mb-4 grid min-h-72 place-items-center border-dashed text-center"><div><Icon name="database" size={38} className="mx-auto text-[#2d826b]"/><h2 className="mt-4 font-bold">Unggah catatan operasional</h2><p className="mt-2 text-sm text-slate-400">CSV atau Excel, maksimal 10 MB. Contoh: data_harian_mei.xlsx</p><button onClick={()=>openDetail('File berhasil diperiksa','90 baris ditemukan. 88 baris siap dipakai dan 2 suhu tidak wajar akan diperbaiki setelah Anda setujui.')} className="mt-5 rounded-xl bg-[#173d32] px-5 py-3 text-sm font-semibold text-white">Pilih file contoh</button></div></article> :
    <div className="grid gap-4 xl:grid-cols-[1.35fr_.65fr]">
      <article className="card"><h2 className="section-title">Kondisi Operasional</h2><p className="section-subtitle">Data rencana operasional hari ini</p><div className="mt-6 grid gap-5 sm:grid-cols-2">
        <Field label="Tanggal" value="19/05/2025"/><label><span className="mb-2 block text-xs font-semibold text-slate-600">Jumlah porsi disiapkan</span><input value={portions} onChange={e=>setPortions(Math.max(0,+e.target.value.trim()))} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"/></label><label><span className="mb-2 block text-xs font-semibold text-slate-600">Jumlah staf dapur</span><input value={staff} onChange={e=>setStaff(+e.target.value)} className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"/></label>
        <label><span className="mb-2 block text-xs font-semibold text-slate-600">Pengalaman staf</span><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"><option>Ahli</option><option>Menengah</option><option>Pemula</option></select></label><Field label="Suhu dapur" value="29" suffix="°C"/><Field label="Kelembapan" value="72" suffix="%"/><Field label="Limbah kemarin (otomatis)" value="14" suffix="kg"/>
        <label><span className="mb-2 block text-xs font-semibold text-slate-600">Kategori utama</span><select className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"><option>Daging</option><option>Susu</option><option>Biji-bijian</option><option>Sayur</option></select></label>
        <label className="flex items-center justify-between rounded-xl bg-slate-50 p-3"><span className="text-xs font-semibold text-slate-600">Ada acara khusus</span><input type="checkbox" defaultChecked className="h-4 w-4 accent-emerald-700"/></label>
        <label className="sm:col-span-2"><span className="mb-2 block text-xs font-semibold text-slate-600">Catatan</span><textarea defaultValue="Reservasi rombongan 24 orang pukul 19.00" className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"/></label>
      </div><div className="mt-5 flex gap-3"><button onClick={() => openDetail('Data tersimpan','Rencana hari ini tersimpan. Perkiraan limbah dan tugas dapur sudah diperbarui.')} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#173d32] py-3 text-sm font-semibold text-white"><Icon name="check" size={17}/>Simpan & Prediksi</button><button onClick={()=>{setPortions(500);setStaff(14)}} className="rounded-xl border border-slate-200 px-5 text-sm font-semibold">Reset</button></div></article>
      <article className="card bg-[#173d32] text-white"><p className="text-xs font-semibold text-emerald-100/65">PRATINJAU LANGSUNG</p><div className="mt-8 text-center"><strong className="text-6xl">{predicted}</strong><span className="ml-2 text-lg text-white/60">kg</span><p className="mt-3 text-sm text-white/55">Sekitar Rp {Math.round(+predicted*15000).toLocaleString('id-ID')}</p><span className="mt-6 inline-flex items-center gap-2 rounded-full bg-orange-400/15 px-4 py-2 text-sm font-semibold text-orange-300"><Icon name="alert" size={16}/>{+predicted>15?'Tinggi':+predicted>=10?'Waspada':'Aman'}</span></div><div className="mt-7 rounded-xl bg-white/8 p-4 text-xs leading-5 text-white/65">Beban {Math.round(portions/staff)} porsi per staf — {portions/staff>35?'Berat':'Normal'}. Kurangi porsi atau tambah staf bila beban melewati 35.</div></article>
    </div>}
    <div className="mt-4 grid gap-4 lg:grid-cols-[1.3fr_.7fr]"><article className="card overflow-x-auto"><h2 className="section-title">5 Input Terakhir</h2><table className="mt-4 w-full min-w-[520px] text-left text-xs"><thead><tr className="text-slate-400">{['Tanggal','Porsi','Staf','Limbah','Aksi'].map(x=><th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{[['18 Mei','520','15','14 kg'],['17 Mei','480','14','12 kg'],['16 Mei','560','16','18 kg'],['15 Mei','450','13','9 kg'],['14 Mei','490','14','11 kg']].map(r=><tr className="border-t border-slate-100" key={r[0]}>{r.map(x=><td className="py-3" key={x}>{x}</td>)}<td><button className="text-emerald-700">Edit</button> · <button className="text-red-500">Hapus</button></td></tr>)}</tbody></table></article><article className="card"><span className="metric-icon green"><Icon name="check"/></span><h3 className="mt-4 font-bold">Data siap dipakai</h3><strong className="mt-2 block text-3xl text-[#173d32]">96% lengkap</strong><p className="mt-2 text-xs leading-5 text-slate-500">12 data tidak wajar diperbaiki otomatis dari 90 hari catatan.</p><button className="mt-4 text-xs font-bold text-emerald-700">Lihat perbaikan</button></article></div>
  </div>

  if (page === 'Prediksi 7 Hari') {
    const days = [
      ['Sen','19 Mei',12,'Waspada',470,34],['Sel','20 Mei',9,'Aman',460,31],['Rab','21 Mei',18,'Tinggi',520,37],['Kam','22 Mei',11,'Waspada',470,32],['Jum','23 Mei',14,'Waspada',490,35],['Sab','24 Mei',19,'Tinggi',540,39],['Min','25 Mei',13,'Waspada',480,34],
    ] as const
    const day = days[selectedDay]
    return <div className="page-enter">
      <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-bold sm:text-[30px]">Rabu & Sabtu berisiko Tinggi</h1><p className="mt-1 text-sm text-slate-500">Potensi hemat minggu ini <strong className="text-emerald-700">Rp320.000</strong>.</p></div><button onClick={()=>openDetail('Rencana siap diekspor','Rencana 7 hari berisi porsi, staf, dan peringatan risiko telah disiapkan sebagai PDF.')} className="rounded-xl bg-[#173d32] px-4 py-3 text-xs font-semibold text-white">Ekspor Rencana PDF</button></div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">{days.map((d,i)=><button key={d[0]} onClick={()=>setSelectedDay(i)} className={`rounded-2xl border p-4 text-left transition ${i===selectedDay?'ring-2 ring-[#173d32]': ''} ${d[3]==='Tinggi'?'border-red-200 bg-red-50':d[3]==='Aman'?'border-emerald-200 bg-emerald-50':'border-amber-200 bg-amber-50'}`}><p className="text-xs text-slate-500">{d[0]} · {d[1]}</p><strong className="mt-3 block text-2xl">{d[2]} kg</strong><span className={`mt-2 inline-block rounded-full px-2 py-1 text-[10px] font-bold ${d[3]==='Tinggi'?'bg-red-100 text-red-700':d[3]==='Aman'?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}`}>{d[3]}</span><p className="mt-3 text-[10px] text-slate-500">Saran {d[4]} porsi<br/>{d[5]} porsi/staf</p></button>)}</div>
      <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_.6fr]"><article className="card"><h2 className="section-title">Limbah 7 Hari Mendatang</h2><div className="mt-6 flex h-64 items-end gap-3 border-b border-slate-200">{days.map((d,i)=><div className="flex h-full flex-1 flex-col items-center justify-end gap-2" key={d[0]}><span className="text-xs font-bold">{d[2]}</span><div className={`w-full max-w-14 rounded-t-lg ${d[2]>15?'bg-red-400':d[2]>=10?'bg-amber-400':'bg-emerald-500'}`} style={{height:`${d[2]*9}px`}}/><span className="text-[10px] text-slate-400">{d[0]}</span></div>)}</div><div className="mt-4 flex gap-4 text-[10px] text-slate-500"><span>Hijau: Aman &lt;10 kg</span><span>Kuning: Waspada 10–15 kg</span><span>Merah: Tinggi &gt;15 kg</span></div></article>
      <article className="card"><h2 className="section-title">Ubah rencana {day[0]}</h2><p className="section-subtitle">Hasil berubah saat input disesuaikan</p><div className="mt-5 space-y-4"><Field label="Porsi" value={String(day[4])}/><Field label="Staf" value={String(Math.round(day[4]/day[5]))}/><Field label="Suhu" value="30°C"/><label className="flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs font-semibold">Acara khusus<input type="checkbox" defaultChecked={day[0]==='Rab'||day[0]==='Sab'} className="accent-emerald-700"/></label></div><button onClick={()=>openDetail('Rencana hari diperbarui',`${day[0]}, ${day[1]} kini memakai rencana ${day[4]} porsi. Tim dapur akan menerima pembaruan.`)} className="mt-5 w-full rounded-xl bg-[#173d32] py-3 text-xs font-bold text-white">Simpan Perubahan</button></article></div>
      <div className="mt-4 grid grid-cols-3 gap-4">{[['Total limbah','96 kg'],['Perkiraan biaya','Rp1.440.000'],['Potensi hemat','Rp320.000']].map(x=><article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-xl text-[#173d32]">{x[1]}</strong></article>)}</div>
    </div>
  }

  if (page === 'Simulasi Porsi') {
    const simWaste = portions >= 475 ? 14+(portions-475)*.08 : portions >= 450 ? 12+(portions-450)*.08 : 11+(portions-425)*.04
    const perStaff = Math.round(portions/staff)
    return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">450 porsi paling seimbang: hemat Rp60.000</h1><p className="mt-1 text-sm text-slate-500">Coba jumlah porsi dan staf untuk mencari rencana paling aman.</p></div>
    <div className="grid gap-4 lg:grid-cols-[.72fr_1.28fr]"><article className="card"><h2 className="section-title">Atur Porsi & Staf</h2><p className="mt-7 text-center text-5xl font-bold text-[#173d32]">{portions}</p><p className="mt-2 text-center text-xs text-slate-400">porsi direncanakan</p><input aria-label="Jumlah porsi" type="range" min="350" max="550" step="5" value={portions} onChange={e=>setPortions(+e.target.value)} className="mt-6 w-full accent-[#2d826b]"/><div className="mt-2 flex justify-between text-[10px] text-slate-400"><span>350</span><span>550</span></div><div className="mt-5 flex justify-between text-xs"><span>Jumlah staf</span><strong>{staff} orang</strong></div><input aria-label="Jumlah staf" type="range" min="8" max="20" value={staff} onChange={e=>setStaff(+e.target.value)} className="mt-3 w-full accent-[#2d826b]"/><div className="mt-5 grid grid-cols-4 gap-2">{[500,475,450,425].map((v,i)=><button onClick={()=>setPortions(v)} key={v} className="rounded-lg bg-slate-100 py-2 text-[10px] font-semibold hover:bg-emerald-100">{i===0?'Awal':`-${i*5}%`}</button>)}</div></article>
    <article className="card"><div className="flex justify-between"><div><h2 className="section-title">Porsi vs Limbah</h2><p className="section-subtitle">Sumbu X: porsi · Sumbu Y: limbah (kg)</p></div><span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">Hemat Rp{Math.max(0,(16-simWaste)*15000).toLocaleString('id-ID')}</span></div><svg viewBox="0 0 620 250" className="mt-4 w-full"><rect x="50" y="25" width="540" height="75" fill="#fee2e2" opacity=".6"/><rect x="50" y="100" width="540" height="50" fill="#fef3c7" opacity=".7"/><rect x="50" y="150" width="540" height="70" fill="#dcfce7" opacity=".6"/>{[5,10,15,20].map(v=><g key={v}><line x1="50" y1={220-v*10} x2="590" y2={220-v*10} stroke="#dce3df"/><text x="42" y={224-v*10} textAnchor="end" fontSize="9">{v} kg</text></g>)}<path d="M75 140 C165 135 220 120 300 100 S445 72 560 50" fill="none" stroke="#27715f" strokeWidth="4"/>{[[350,8],[425,11],[450,12],[475,14],[500,16],[550,18]].map(([p,w])=><circle key={p} cx={75+(p-350)*2.425} cy={220-w*10} r="5" fill="white" stroke="#27715f" strokeWidth="3"/>)}<circle cx={75+(portions-350)*2.425} cy={220-simWaste*10} r="8" fill="#e99a3d" stroke="white" strokeWidth="3"/><text x={75+(portions-350)*2.425} y={205-simWaste*10} textAnchor="middle" fontSize="9" fontWeight="700">Pilihan: {simWaste.toFixed(1)} kg</text>{[350,400,450,500,550].map(p=><text key={p} x={75+(p-350)*2.425} y="240" textAnchor="middle" fontSize="9">{p}</text>)}</svg></article></div>
    {portions<425 && <div className="mt-4 flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><Icon name="alert"/>Porsi terlalu sedikit bisa membuat pelanggan kehabisan menu.</div>}
    <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">{[['Prediksi',`${simWaste.toFixed(1)} kg`],['Hemat',`Rp${Math.max(0,(16-simWaste)*15000).toLocaleString('id-ID')}`],['Beban staf',`${perStaff} porsi/orang`],['Risiko kehabisan',portions<425?'Tinggi':portions<450?'Sedang':'Rendah']].map(x=><article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-xl text-[#173d32]">{x[1]}</strong><button className="mt-3 text-[10px] font-bold text-emerald-700">Lihat saran</button></article>)}</div>
    <article className="card mt-4 overflow-x-auto"><h2 className="section-title">Perbandingan 4 Skenario</h2><table className="mt-4 w-full min-w-[620px] text-left text-xs"><thead><tr className="text-slate-400">{['Skenario','Porsi','Limbah','Hemat','Risiko kehabisan'].map(x=><th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{[['Awal','500','16 kg','Rp0','Rendah'],['−5%','475','14 kg','Rp30.000','Rendah'],['−10%','450','12 kg','Rp60.000','Sedang'],['−15%','425','11 kg','Rp75.000','Sedang']].map(r=><tr className="border-t border-slate-100" key={r[0]}>{r.map(x=><td className="py-3" key={x}>{x}</td>)}</tr>)}</tbody></table><div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="text-[10px] text-slate-400">Ini perkiraan, bukan jaminan.</p><div className="flex gap-2"><button onClick={()=>openDetail('Skenario tersimpan',`Skenario ${portions} porsi dan ${staff} staf disimpan.`)} className="rounded-lg border px-3 py-2 text-xs font-bold">Simpan Skenario</button><button onClick={()=>applyPlan(portions,staff,simWaste)} className="rounded-lg bg-[#173d32] px-3 py-2 text-xs font-bold text-white">Jadikan Rencana Hari Ini</button></div></div></article>
  </div>
  }

  if (page === 'Insight & Penyebab') return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">Penyebab terbesar limbah: acara khusus (+2,1 kg)</h1><p className="mt-1 text-sm text-slate-500">Pola dari 90 hari catatan restoran Anda, bukan kepastian.</p></div>
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">{[['Jumat paling boros','+6 kg','Kurangi persiapan awal 8%.'],['Staf ahli lebih hemat','−2 kg/hari','Pasangkan staf ahli saat ramai.'],['Daging naik 3 hari','+3 kg','Periksa pembelian dan penyimpanan.']].map((x,i)=><article className={`rounded-xl border p-4 ${i===1?'border-emerald-200 bg-emerald-50':'border-red-200 bg-red-50'}`} key={x[0]}><Icon name={i===1?'check':'alert'} size={17}/><p className="mt-2 text-xs font-semibold">{x[0]}</p><strong className="mt-1 block text-lg">{x[1]}</strong><p className="mt-1 text-[10px] text-slate-500">{x[2]}</p><button className="mt-2 text-[10px] font-bold text-emerald-800">Terapkan saran</button></article>)}</div>
    <div className="grid gap-4 lg:grid-cols-[1.15fr_.85fr]"><article className="card"><h2 className="section-title">Hal yang Paling Memengaruhi Limbah</h2><p className="section-subtitle">Dampak rata-rata (kg)</p><div className="mt-6 space-y-4">{[['Porsi terlalu banyak',2.8,'red'],['Acara khusus',2.1,'red'],['Beban staf berat',1.9,'red'],['Akhir pekan',1.2,'red'],['Staf berpengalaman',-1.7,'green']].map(([a,b,c])=><div key={String(a)}><div className="mb-1 flex justify-between text-xs"><span>{a}</span><strong className={c==='red'?'text-red-600':'text-emerald-700'}>{Number(b)>0?'+':''}{b} kg</strong></div><div className="h-3 rounded-full bg-slate-100"><div className={`h-full rounded-full ${c==='red'?'bg-red-400':'bg-emerald-500'}`} style={{width:`${Math.abs(Number(b))*28}%`}}/></div></div>)}</div></article><article className="card"><h2 className="section-title">Limbah per Kategori</h2><p className="section-subtitle">Proporsi 911 catatan · 40.851,7 kg</p><div className="mt-5 flex items-center gap-5"><Donut insight/><div className="space-y-3 text-xs">{wasteComposition.map(({ label, value })=><p key={label}><strong>{value}%</strong> {label}</p>)}</div></div></article></div>
    <div className="mt-4 grid gap-4 lg:grid-cols-2"><article className="card"><h2 className="section-title">Staf & Beban Kerja</h2><div className="mt-6 flex h-40 items-end justify-around">{[['Pemula',17],['Menengah',13],['Ahli',10]].map(([a,b])=><div className="flex flex-col items-center gap-2" key={a}><strong className="text-xs">{b} kg</strong><div className="w-16 rounded-t-lg bg-[#2d826b]" style={{height:`${Number(b)*6}px`}}/><span className="text-xs text-slate-500">{a}</span></div>)}</div><p className="mt-5 rounded-xl bg-amber-50 p-3 text-xs text-amber-800">Jika 1 staf menangani lebih dari 35 porsi, limbah naik sekitar 2 kg. <strong>Tambah 1 staf pada Sabtu.</strong></p><button onClick={()=>openDetail('Saran staf ideal','Gunakan 16 staf pada Sabtu untuk menurunkan beban dari 39 menjadi 34 porsi per staf. Potensi hemat 2 kg atau Rp30.000.')} className="mt-4 text-xs font-bold text-emerald-700">Saran jumlah staf ideal →</button></article><article className="card"><h2 className="section-title">Hari Paling Boros dalam 4 Minggu</h2><div className="mt-5 grid grid-cols-7 gap-2">{Array.from({length:28},(_,i)=><div title={`${6+(i*7)%19} kg`} key={i} className={`aspect-square rounded-md ${i%7===4?'bg-red-400':i%7===5?'bg-amber-400':i%3===0?'bg-emerald-300':'bg-emerald-100'}`}/>)}</div><div className="mt-3 flex justify-between text-[10px] text-slate-400"><span>Sen</span><span>Sel</span><span>Rab</span><span>Kam</span><span>Jum</span><span>Sab</span><span>Min</span></div><div className="mt-5 grid grid-cols-2 gap-3"><div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs">Hari biasa</p><strong className="text-xl">11,8 kg</strong></div><div className="rounded-xl bg-red-50 p-4"><p className="text-xs">Acara khusus</p><strong className="text-xl">15,9 kg</strong></div></div></article></div>
  </div>

  const rangeScale = reportRange === 'Mingguan' ? .24 : reportRange === 'Kustom' ? .55 : 1
  const categoryScale: Record<string, number> = {'Semua kategori':1,Daging:.43,Sayur:.2,Susu:.19,'Biji-bijian':.18}
  const reportScale = rangeScale * categoryScale[reportCategory]
  const totalWaste = Math.round(342 * reportScale)
  const totalSaved = Math.round(28 * reportScale)
  const rows = [
    ['19 Mei','500','14','Daging','12 kg','Waspada','Rp45.000'],
    ['18 Mei','520','15','Sayur','14 kg','Waspada','Rp30.000'],
    ['17 Mei','480','14','Susu','9 kg','Aman','Rp60.000'],
    ['16 Mei','560','16','Daging','18 kg','Tinggi','Rp15.000'],
    ['15 Mei','450','13','Biji-bijian','9 kg','Aman','Rp75.000'],
    ['14 Mei','490','14','Sayur','11 kg','Waspada','Rp45.000'],
  ].filter(r=>(reportCategory==='Semua kategori'||r[3]===reportCategory)&&r.join(' ').toLowerCase().includes(search.toLowerCase()))
  const finishExport = () => {
    if (exportType === 'Unduh PDF') {
      window.print()
    } else if (exportType === 'Unduh Excel') {
      const table = [
        ['Tanggal','Porsi','Staf','Kategori','Limbah','Risiko','Hemat'],
        ...rows,
      ]
      const html = `<table>${table.map(row=>`<tr>${row.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</table>`
      const url = URL.createObjectURL(new Blob([html], { type: 'application/vnd.ms-excel' }))
      const link = document.createElement('a')
      link.href = url
      link.download = `FoodSave-${reportRange}-Mei-2025.xls`
      link.click()
      URL.revokeObjectURL(url)
    } else {
      openDetail('Pratinjau email siap','Penerima, subjek, pesan, dan lampiran sudah diperiksa. Hubungkan layanan email untuk melakukan pengiriman nyata.')
    }
    setExportType(null)
  }
  return <div className="page-enter">
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><h1 className="text-2xl font-bold sm:text-[30px]">Limbah turun 18%: hemat Rp{(totalSaved*15000).toLocaleString('id-ID')}</h1><p className="mt-1 text-sm text-slate-500">Ringkasan {reportRange.toLowerCase()} · {reportCategory.toLowerCase()}.</p></div><div className="flex gap-2">{['Unduh PDF','Unduh Excel','Kirim ke Email'].map(x=><button onClick={()=>setExportType(x)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold" key={x}>{x}</button>)}</div></div>
    <div className="mb-4 flex flex-wrap gap-2">{['Mingguan','Bulanan','Kustom'].map(x=><button onClick={()=>setReportRange(x)} className={`rounded-full px-4 py-2 text-xs font-semibold ${reportRange===x?'bg-[#173d32] text-white':'bg-white'}`} key={x}>{x}</button>)}<select value={reportCategory} onChange={e=>setReportCategory(e.target.value)} className="rounded-full border-0 bg-white px-4 text-xs"><option>Semua kategori</option><option>Daging</option><option>Sayur</option><option>Susu</option><option>Biji-bijian</option></select>{reportRange==='Kustom'&&<><input type="date" defaultValue="2025-05-08" className="rounded-full border-0 bg-white px-4 text-xs"/><input type="date" defaultValue="2025-05-24" className="rounded-full border-0 bg-white px-4 text-xs"/></>}</div>
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">{[['Total limbah',`${totalWaste} kg`],['Total biaya',`Rp${(totalWaste*15000).toLocaleString('id-ID')}`],['Berhasil dihemat',`${totalSaved} kg`],['Dibanding lalu','↓ 18%'],['Terbaik / Terburuk','Selasa / Jumat']].map(x=><article className="card" key={x[0]}><p className="text-xs text-slate-400">{x[0]}</p><strong className="mt-2 block text-lg text-[#173d32]">{x[1]}</strong></article>)}</div>
    <div className="mt-4 grid gap-4 lg:grid-cols-[1.2fr_.8fr]"><article className="card"><h2 className="section-title">Tren Limbah Bulan Mei</h2><p className="section-subtitle">Tanggal vs limbah (kg)</p><TrendChart/></article><article className="card"><h2 className="section-title">Temuan Utama</h2><ol className="mt-5 space-y-3">{['Jumat rata-rata 6 kg lebih boros.','Acara khusus menambah sekitar 2,1 kg.','Staf ahli menghemat sekitar 2 kg per hari.','Daging menyumbang 43% dari total limbah.','Pengurangan 10% porsi paling seimbang.'].map((x,i)=><li className="flex gap-3 text-xs leading-5" key={x}><span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-100 font-bold text-emerald-700">{i+1}</span>{x}</li>)}</ol><h3 className="mt-6 text-sm font-bold">Rekomendasi Bulan Depan</h3><ul className="mt-3 space-y-2 text-xs text-slate-600"><li>1. Turunkan persiapan Jumat sebesar 8%.</li><li>2. Tambah satu staf ahli pada Sabtu.</li><li>3. Batasi pembelian daging 12 kg per minggu.</li></ul></article></div>
    <article className="card mt-4"><div className="flex items-center justify-between gap-4"><h2 className="section-title">Rincian Harian</h2><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cari tanggal atau status" className="rounded-lg border border-slate-200 px-3 py-2 text-xs"/></div><div className="mt-4 overflow-x-auto"><table className="w-full min-w-[720px] text-left text-xs"><thead><tr className="text-slate-400">{['Tanggal','Porsi','Staf','Kategori','Limbah','Risiko','Hemat'].map(x=><th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{rows.map(r=><tr className="border-t border-slate-100" key={r[0]}>{r.map(x=><td className="py-3" key={x}>{x}</td>)}</tr>)}</tbody></table></div></article>
    {exportType&&<div className="fixed inset-0 z-[80] grid place-items-center bg-slate-950/40 p-4" onMouseDown={()=>setExportType(null)}><article onMouseDown={e=>e.stopPropagation()} className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl"><div className="flex justify-between"><div><p className="text-xs font-semibold text-emerald-700">SIAPKAN LAPORAN</p><h3 className="mt-1 text-xl font-bold">{exportType}</h3></div><button onClick={()=>setExportType(null)}><Icon name="close"/></button></div>{exportType==='Kirim ke Email'?<div className="mt-6 space-y-4"><Field label="Penerima email" value="owner@foodsave.id"/><Field label="Subjek" value={`Laporan ${reportRange} FoodSave — Mei 2025`}/><label className="block"><span className="mb-2 block text-xs font-semibold">Pesan</span><textarea defaultValue={`Halo, berikut laporan ${reportRange.toLowerCase()} FoodSave Restaurant. Total limbah ${totalWaste} kg dan penghematan ${totalSaved} kg. Mohon tinjau rekomendasi operasional terlampir.`} className="min-h-28 w-full rounded-xl border border-slate-200 p-3 text-sm"/></label><p className="text-xs text-slate-400">Lampiran: FoodSave-Mei-2025.pdf · Pratinjau, belum dikirim</p></div>:<div className="mt-6 space-y-4"><Field label="Nama file" value={`FoodSave-${reportRange}-Mei-2025.${exportType==='Unduh PDF'?'pdf':'xls'}`}/><div className="rounded-xl bg-slate-50 p-4 text-xs leading-5 text-slate-600">Isi: ringkasan biaya, grafik tren, temuan utama, rekomendasi, dan rincian harian. Filter aktif: <strong>{reportRange} · {reportCategory}</strong>.</div><label className="flex items-center gap-2 text-xs"><input type="checkbox" defaultChecked className="accent-emerald-700"/> Sertakan grafik dan rekomendasi</label></div>}<button onClick={finishExport} className="mt-6 w-full rounded-xl bg-[#173d32] py-3 text-sm font-bold text-white">{exportType==='Kirim ke Email'?'Buka Pratinjau Email':exportType==='Unduh PDF'?'Buka Dialog PDF':'Unduh File Excel'}</button></article></div>}
  </div>
}

function App({ user, onLogout }: { user: AppUser; onLogout?: () => void | Promise<void> }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [active, setActive] = useState('Overview')
  const [detail, setDetail] = useState<{title: string; body: string} | null>(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [composition, setComposition] = useState(wasteComposition)
  const [prediction, setPrediction] = useState({ value: 12, lower: 10, upper: 15 })

  useEffect(() => {
    getOperationalInsights()
      .then((items) => {
        if (items.length) setComposition(items)
      })
      .catch(() => undefined)
  }, [])

  useEffect(() => {
    getDashboard()
      .then((data) => {
        if (!data.prediction) return
        setPrediction({
          value: Number(data.prediction.predicted_waste_kg ?? 12),
          lower: Number(data.prediction.interval_lower_kg ?? 10),
          upper: Number(data.prediction.interval_upper_kg ?? 15),
        })
      })
      .catch(() => undefined)
  }, [])

  return <div className="min-h-screen bg-[#f5f7f4] text-[#1e2d28]">
    <Sidebar open={menuOpen} close={() => setMenuOpen(false)} active={active} onNavigate={setActive} onProfile={()=>setAccountOpen(true)} user={user}/>
    <main className="lg:ml-[264px]">
      <header className="sticky top-0 z-30 flex h-[76px] items-center border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-md sm:px-7 lg:px-9">
        <button onClick={() => setMenuOpen(true)} className="mr-3 rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"><Icon name="menu"/></button>
        <div><p className="text-lg font-bold tracking-tight sm:text-xl">{active}</p><p className="hidden text-xs text-slate-400 sm:block">Analisis operasional untuk keputusan berbasis data</p></div>
        <div className="ml-auto flex items-center gap-2.5">
          <button onClick={()=>setDetail({title:'3 perhatian hari ini',body:'Limbah daging naik 3 hari, acara khusus besok, dan beban staf Sabtu diperkirakan berat.'})} className="relative grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-500"><Icon name="bell" size={18}/><span className="absolute right-1.5 top-1.5 grid h-4 w-4 place-items-center rounded-full bg-orange-500 text-[9px] text-white">3</span></button>
          <button onClick={()=>setDetail({title:'Pilih periode laporan',body:'Periode aktif: 1–30 Mei 2025. Data berisi 30 hari operasional, 14.620 porsi, dan total limbah 342 kg.'})} className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-600 sm:flex"><Icon name="calendar" size={16}/> 1–30 Mei 2025 <Icon name="chevron" size={13}/></button>
        </div>
      </header>

      <div className="mx-auto max-w-[1480px] p-4 sm:p-7 lg:p-9">
        {active === 'Overview' ? <>
        <section className="mb-4 grid gap-4 lg:grid-cols-[1.25fr_.75fr]">
          <article className="card overflow-hidden bg-[#173d32] text-white"><div className="grid items-center gap-5 sm:grid-cols-[180px_1fr]"><div className="relative mx-auto grid h-40 w-40 place-items-center rounded-full bg-[conic-gradient(#f4b844_0_62%,#ffffff18_62%)]"><div className="grid h-28 w-28 place-items-center rounded-full bg-[#173d32] text-center"><div><Icon name="alert" className="mx-auto text-amber-300"/><strong className="mt-1 block text-lg text-amber-300">Waspada</strong><span className="text-[10px] text-white/50">Risiko hari ini</span></div></div></div><div><p className="text-sm text-white/55">Prediksi limbah hari ini</p><h2 className="mt-2 text-4xl font-bold">{prediction.value.toFixed(1)} kg</h2><p className="mt-2 text-sm text-white/55">Rentang {prediction.lower.toFixed(1)}–{prediction.upper.toFixed(1)} kg · biasanya meleset ±1,2 kg</p><div className="mt-4 flex flex-wrap gap-2 text-[10px]"><span className="rounded-full bg-white/10 px-3 py-1.5">Acara khusus ↑</span><span className="rounded-full bg-white/10 px-3 py-1.5">Staf ahli ↓</span><span className="rounded-full bg-white/10 px-3 py-1.5">Limbah kemarin tinggi ↑</span></div></div></div></article>
          <article className="card border-l-4 border-l-emerald-500"><span className="metric-icon green"><Icon name="leaf"/></span><p className="mt-4 text-sm font-semibold">Saran paling berdampak</p><h3 className="mt-2 text-2xl font-bold text-[#173d32]">Kurangi 30 porsi</h3><p className="mt-2 text-sm text-slate-500">Hemat sekitar <strong>3 kg / Rp45.000</strong> hari ini tanpa mengganggu cadangan.</p><button onClick={()=>setDetail({title:'Rencana diterapkan',body:'Jumlah persiapan diubah dari 500 menjadi 470 porsi. Tim dapur akan melihat rencana terbaru.'})} className="mt-5 w-full rounded-xl bg-emerald-100 py-3 text-xs font-bold text-emerald-800">Terapkan Saran</button></article>
        </section>
        <section className="mb-7">
          <div><p className="mb-1 text-sm font-medium text-[#2d826b]">Senin, 19 Mei 2025</p><h1 className="text-2xl font-bold tracking-tight sm:text-[30px]">Jumat paling boros: rata-rata 18 kg</h1><p className="mt-1 text-sm text-slate-500">Fokus minggu ini: kurangi persiapan berlebih sebelum akhir pekan.</p></div>
        </section>

        <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[
            {label:'Rata-rata 7 Hari',value:'12,4',unit:'kg/hari',icon:'leaf',note:'↓ 8% dari minggu lalu',tone:'green'},
            {label:'Biaya Limbah Bulan Ini',value:'Rp5,13',unit:'juta',icon:'database',note:'↓ Rp420.000',tone:'lime'},
            {label:'Berhasil Dihemat',value:'28',unit:'kg',icon:'spark',note:'Senilai Rp420.000',tone:'blue'},
            {label:'Hari Risiko Tinggi',value:'4',unit:'hari',icon:'alert',note:'2 hari lebih sedikit',tone:'orange'},
          ].map((m) => <article key={m.label} className="card group min-h-[158px]">
            <div className="flex items-start justify-between"><p className="text-sm font-medium text-slate-500">{m.label}</p><span className={`metric-icon ${m.tone}`}><Icon name={m.icon as IconName} size={19}/></span></div>
            <div className="mt-5 flex items-baseline gap-1.5"><strong className={`text-[28px] font-bold tracking-tight ${m.tone === 'orange' ? 'text-[#b75f24]' : 'text-[#173d32]'}`}>{m.value}</strong><span className="text-xs font-medium text-slate-400">{m.unit}</span></div>
            <p className={`mt-2 text-xs ${m.tone === 'orange' ? 'text-orange-600' : m.tone === 'lime' ? 'text-emerald-600' : 'text-slate-400'}`}>{m.note}</p>
          </article>)}
        </section>

        <section className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.8fr)_minmax(320px,.8fr)]">
          <article className="card">
            <div className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="section-title">Perbandingan Aktual vs Prediksi</h2><p className="section-subtitle">30 hari terakhir · sumbu dalam kilogram</p></div><span className="rounded-lg bg-[#f2f4f1] px-3 py-2 text-[11px] font-semibold text-[#1f5b4c]">30 Hari</span></div>
            <TrendChart/>
          </article>
          <article className="card flex flex-col">
            <h2 className="section-title">Komposisi Waste</h2><p className="section-subtitle">Proporsi limbah aktual dari data kategori</p>
            <div className="flex flex-1 flex-col items-center justify-center gap-4 py-4 sm:flex-row xl:flex-col 2xl:flex-row"><Donut composition={composition}/><div className="w-full space-y-3">
              {composition.map(({ label, value, color })=><div key={label} className="flex items-center text-xs"><i className="mr-2.5 h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }}/><span className="text-slate-500">{label}</span><strong className="ml-auto text-slate-700">{value}%</strong></div>)}
            </div></div>
          </article>
        </section>

        <section className="mt-4 grid gap-4 xl:grid-cols-[1.1fr_.9fr]">
          <article className="card">
            <div className="flex items-start justify-between"><div><h2 className="section-title">Rekomendasi Hari Ini</h2><p className="section-subtitle">Saran berdasarkan prediksi model</p></div><span className="rounded-full bg-[#edf7d5] px-3 py-1 text-[10px] font-bold text-[#54752b]">3 SARAN</span></div>
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              {[
                ['Kurangi 8% porsi','Siapkan 460 dari rencana 500 porsi.','green'],
                ['Prioritaskan bahan','Gunakan bahan mendekati masa simpan.','lime'],
                ['Pantau jam 14.00','Evaluasi sisa untuk layanan malam.','orange'],
              ].map(([title,desc,tone],i)=><button onClick={()=>setDetail({title, body:i===0?'Berdasarkan pola permintaan hari Senin, kurangi 40 porsi dari rencana awal. Estimasi waste turun dari 16 kg menjadi 13 kg dengan buffer permintaan tetap aman.':i===1?'Dahulukan sayuran hijau, dairy, dan bahan siap olah dengan masa simpan kurang dari 48 jam. Terapkan metode FIFO pada persiapan makan siang.':'Lakukan stock opname singkat pukul 14.00. Jika sisa porsi lebih dari 18%, alihkan bahan yang aman ke menu malam atau program donasi.'})} key={title} className="group rounded-xl border border-slate-100 bg-[#fafbf9] p-4 text-left transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-sm"><span className={`mb-4 grid h-8 w-8 place-items-center rounded-lg ${tone==='green'?'bg-emerald-100 text-emerald-700':tone==='lime'?'bg-lime-100 text-lime-700':'bg-orange-100 text-orange-700'}`}><Icon name={i===0?'trend':i===1?'leaf':'alert'} size={16}/></span><p className="text-sm font-semibold">{title}</p><p className="mt-1.5 text-[11px] leading-5 text-slate-400">{desc}</p><span className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-[#2d826b]">Lihat detail <Icon name="arrow" size={13}/></span></button>)}
            </div>
          </article>
          <article className="card">
            <div className="flex items-start justify-between"><div><h2 className="section-title">Target Pengurangan</h2><p className="section-subtitle">Progres target waste bulan Mei</p></div><span className="text-xs font-semibold text-[#2d826b]">18 hari lagi</span></div>
            <div className="mt-7 flex items-end justify-between"><div><strong className="text-3xl font-bold text-[#173d32]">72%</strong><p className="mt-1 text-xs text-slate-400">dari target bulanan</p></div><p className="text-right text-xs leading-5 text-slate-500"><strong className="text-slate-700">86,4 kg</strong> terselamatkan<br/>Target 120 kg</p></div>
            <div className="mt-5 h-2.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full w-[72%] rounded-full bg-gradient-to-r from-[#2d826b] to-[#b9d85d]"/></div>
            <div className="mt-5 flex items-center gap-2 rounded-xl bg-[#f3f8e8] px-4 py-3 text-xs text-[#4d6a2c]"><Icon name="trend" size={16}/><span><strong>Bagus!</strong> 12% lebih baik dari bulan lalu.</span></div>
          </article>
        </section>
        <p className="pb-2 pt-7 text-center text-[10px] text-slate-400">Data contoh (demo) • Diperbarui 5 menit yang lalu</p>
        </> : <AnalysisPage page={active} openDetail={(title,body)=>setDetail({title,body})} applyPlan={(portions,staff,waste)=>{setActive('Input Data Harian');setDetail({title:'Rencana dibawa ke Input Data Harian',body:`Skenario ${portions} porsi, ${staff} staf, dan perkiraan ${waste.toFixed(1)} kg sudah dipindahkan. Periksa kondisi operasional lalu tekan Simpan & Prediksi.`})}}/>}
      </div>
    </main>
    {detail && <div className="fixed inset-0 z-[70] grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm" onMouseDown={()=>setDetail(null)}><article onMouseDown={e=>e.stopPropagation()} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between"><span className="grid h-10 w-10 place-items-center rounded-xl bg-emerald-100 text-emerald-700"><Icon name="spark" size={19}/></span><button onClick={()=>setDetail(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><Icon name="close" size={18}/></button></div><h3 className="mt-5 text-xl font-bold text-[#173d32]">{detail.title}</h3><p className="mt-3 text-sm leading-6 text-slate-500">{detail.body}</p><div className="mt-5 rounded-xl bg-[#f3f8e8] p-4 text-xs leading-5 text-[#4d6a2c]"><strong>Catatan keputusan:</strong> Evaluasi kembali setelah layanan selesai dan catat realisasi waste untuk meningkatkan akurasi model.</div><button onClick={()=>setDetail(null)} className="mt-5 w-full rounded-xl bg-[#173d32] py-3 text-sm font-semibold text-white">Mengerti</button></article></div>}
    {accountOpen && <div className="fixed inset-0 z-[70] flex justify-end bg-slate-950/30" onMouseDown={()=>setAccountOpen(false)}><aside onMouseDown={e=>e.stopPropagation()} className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><div><p className="text-xs font-semibold text-emerald-700">AKUN MANAGER</p><h2 className="mt-1 text-xl font-bold">{user.name}</h2></div><button onClick={()=>setAccountOpen(false)}><Icon name="close"/></button></div><div className="mt-7 rounded-2xl bg-[#173d32] p-5 text-white"><div className="grid h-12 w-12 place-items-center rounded-full bg-[#ebc8a8] font-bold text-[#513a2d]">{user.name.split(' ').map(x=>x[0]).slice(0,2).join('').toUpperCase()}</div><p className="mt-4 font-bold">{user.restaurantName}</p><p className="mt-1 text-xs text-white/55">{user.email}</p><span className="mt-4 inline-flex items-center gap-2 rounded-full bg-emerald-400/15 px-3 py-1.5 text-xs text-emerald-200"><Icon name="check" size={14}/>{hasApiUrl ? 'API tersambung' : 'Mode frontend aktif'}</span></div><div className="mt-5 space-y-3 text-sm"><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Peran</span><strong>Restaurant Manager</strong></div><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Data</span><strong>{hasApiUrl ? 'Data API' : 'Demo siap migrasi'}</strong></div><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Endpoint</span><strong className={hasApiUrl ? 'text-emerald-700' : 'text-amber-700'}>{hasApiUrl ? 'FastAPI v1' : 'Belum diatur'}</strong></div></div><p className="mt-5 text-xs leading-5 text-slate-400">{hasApiUrl ? 'Data kategori limbah diambil dari endpoint insight operasional saat tersedia.' : 'Atur NEXT_PUBLIC_API_URL untuk menghubungkan login dan data kategori ke FastAPI.'}</p><button onClick={()=>{if(onLogout) void onLogout(); else setAccountOpen(false)}} className="mt-6 w-full rounded-xl bg-[#173d32] py-3 text-sm font-bold text-white">{onLogout && hasApiUrl ? 'Keluar dari akun' : 'Tutup panel'}</button></aside></div>}
  </div>
}

export default App
