'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { getNotifications, getReportSummary, getSettings, markNotificationRead, updateSettings, type Notification, type Settings } from '@/lib/api'
import { addDays, kg, longDate, rangeLabel, roleLabel, rupiah, todayIso } from '@/lib/format'
import { AppContext, PAGES, errorText, type AppContextValue, type AppUser, type Page } from '@/components/context'
import { Field, Icon, type IconName } from '@/components/ui'
import Overview from '@/components/Overview'
import InputHarian from '@/components/InputHarian'
import Prediksi7Hari from '@/components/Prediksi7Hari'
import SimulasiPorsi from '@/components/SimulasiPorsi'
import Insight from '@/components/Insight'
import Laporan from '@/components/Laporan'

export type { AppUser }

const icons: Record<Page, IconName> = {
  Overview: 'grid',
  'Input Data Harian': 'database',
  'Prediksi 7 Hari': 'spark',
  'Simulasi Porsi': 'chart',
  'Insight & Penyebab': 'trend',
  Laporan: 'calendar',
}

const initials = (name: string) => name.split(' ').map((x) => x[0]).slice(0, 2).join('').toUpperCase()

function Sidebar({ open, close, active, onNavigate, onProfile, user }: { open: boolean; close: () => void; active: Page; onNavigate: (page: Page) => void; onProfile: () => void; user: AppUser }) {
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
        {PAGES.map((label) => <button key={label} onClick={() => { onNavigate(label); close() }} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${active === label ? 'bg-white/12 font-semibold text-white shadow-inner' : 'text-emerald-50/65 hover:bg-white/7 hover:text-white'}`}><Icon name={icons[label]}/>{label}{active === label && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#c7ef5d]"/>}</button>)}
      </nav>
      <div className="mt-auto rounded-2xl border border-white/10 bg-white/[.06] p-4">
        <div className="mb-3 grid h-9 w-9 place-items-center rounded-lg bg-[#c7ef5d]/15 text-[#c7ef5d]"><Icon name="leaf" size={19}/></div>
        <p className="text-sm font-semibold">Kurangi waste hari ini</p>
        <p className="mt-1 text-xs leading-5 text-emerald-50/55">Setiap kilogram yang diselamatkan membuat dampak.</p>
      </div>
      <button onClick={onProfile} className="mt-4 flex items-center gap-3 border-t border-white/10 px-2 pt-5 text-left">
        <div className="grid h-9 w-9 place-items-center rounded-full bg-[#ebc8a8] text-xs font-bold text-[#513a2d]">{initials(user.name)}</div>
        <div className="min-w-0"><p className="truncate text-sm font-semibold">{user.name}</p><p className="text-[11px] text-white/45">{roleLabel[user.role] ?? user.role}</p></div>
        <Icon name="chevron" size={16} className="ml-auto text-white/35"/>
      </button>
    </aside>
  </>
}

type Detail = { title: string; body: string; error?: boolean }

function App({ user, onLogout }: { user: AppUser; onLogout: () => void | Promise<void> }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [active, setActive] = useState<Page>('Overview')
  const [detail, setDetail] = useState<Detail | null>(null)
  const [accountOpen, setAccountOpen] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const [settings, setSettings] = useState<Settings | null>(null)
  const [version, setVersion] = useState(0)
  const [focusDate, setFocusDate] = useState<string | null>(null)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [today, setToday] = useState(todayIso)

  // Tanggal ikut berganti bila aplikasi dibiarkan terbuka melewati tengah malam.
  useEffect(() => {
    const timer = window.setInterval(() => setToday((current) => (current === todayIso() ? current : todayIso())), 60_000)
    return () => window.clearInterval(timer)
  }, [])

  const openDetail = useCallback((title: string, body: string) => setDetail({ title, body }), [])
  const fail = useCallback((title: string, error: unknown) => setDetail({ title, body: errorText(error), error: true }), [])
  const refresh = useCallback(() => setVersion((value) => value + 1), [])
  const clearFocus = useCallback(() => setFocusDate(null), [])
  const navigate = useCallback((page: Page, date?: string) => { setFocusDate(date ?? null); setActive(page); window.scrollTo({ top: 0 }) }, [])

  useEffect(() => { getSettings().then(setSettings).catch((error) => fail('Pengaturan restoran belum dapat dimuat', error)) }, [fail])
  useEffect(() => { getNotifications().then(setNotifications).catch(() => undefined) }, [version])

  const context: AppContextValue = useMemo(() => ({
    user, settings, setSettings, today, version, refresh, navigate, focusDate, clearFocus, openDetail, fail,
    canEdit: user.role === 'owner' || user.role === 'manager',
  }), [user, settings, today, version, refresh, navigate, focusDate, clearFocus, openDetail, fail])

  const unread = notifications.filter((item) => !item.read_at).length
  const periodStart = addDays(today, -29)

  async function showPeriod() {
    try {
      const summary = await getReportSummary(periodStart, today)
      openDetail('Periode 30 hari terakhir', `${rangeLabel(periodStart, today)}: ${summary.operation_count} hari operasional, ${summary.total_portions.toLocaleString('id-ID')} porsi, total limbah aktual ${kg(summary.total_actual_waste_kg)} kg (${summary.actual_recorded_count} hari ditimbang), perkiraan biaya ${rupiah(summary.estimated_actual_waste_cost)}.`)
    } catch (error) {
      fail('Ringkasan periode belum dapat dimuat', error)
    }
  }

  async function readNotification(item: Notification) {
    if (item.read_at) return
    try {
      const updated = await markNotificationRead(item.id)
      setNotifications((list) => list.map((note) => (note.id === item.id ? updated : note)))
    } catch (error) {
      fail('Notifikasi belum dapat ditandai', error)
    }
  }

  const page = { Overview: <Overview/>, 'Input Data Harian': <InputHarian/>, 'Prediksi 7 Hari': <Prediksi7Hari/>, 'Simulasi Porsi': <SimulasiPorsi/>, 'Insight & Penyebab': <Insight/>, Laporan: <Laporan/> }[active]

  return <AppContext.Provider value={context}><div className="min-h-screen bg-[#f5f7f4] text-[#1e2d28]">
    <Sidebar open={menuOpen} close={() => setMenuOpen(false)} active={active} onNavigate={(next) => navigate(next)} onProfile={() => setAccountOpen(true)} user={user}/>
    <main className="lg:ml-[264px]">
      <header className="sticky top-0 z-30 flex h-[76px] items-center border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-md sm:px-7 lg:px-9">
        <button onClick={() => setMenuOpen(true)} className="mr-3 rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"><Icon name="menu"/></button>
        <div><p className="text-lg font-bold tracking-tight sm:text-xl">{active}</p><p className="hidden text-xs text-slate-400 sm:block">Hari ini, {longDate(today)} · {user.restaurantName}</p></div>
        <div className="ml-auto flex items-center gap-2.5">
          <button aria-label="Notifikasi" onClick={() => setNotesOpen(true)} className="relative grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-500"><Icon name="bell" size={18}/>{unread > 0 && <span className="absolute right-1.5 top-1.5 grid h-4 min-w-4 place-items-center rounded-full bg-orange-500 px-0.5 text-[9px] text-white">{unread > 9 ? '9+' : unread}</span>}</button>
          <button onClick={showPeriod} className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-600 sm:flex"><Icon name="calendar" size={16}/> {rangeLabel(periodStart, today)} <Icon name="chevron" size={13}/></button>
        </div>
      </header>

      <div className="mx-auto max-w-[1480px] p-4 sm:p-7 lg:p-9">
        {settings && Number(settings.ingredient_cost_per_kg) === 0 && <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><Icon name="alert"/><span className="flex-1">Harga bahan per kg belum diisi, jadi semua biaya dan penghematan tampil Rp0.</span><button onClick={() => setAccountOpen(true)} className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-amber-800">Isi di Pengaturan</button></div>}
        <div key={active}>{page}</div>
      </div>
    </main>
    {detail && <div className="fixed inset-0 z-[90] grid place-items-center bg-slate-950/40 p-4 backdrop-blur-sm" onMouseDown={() => setDetail(null)}><article role="dialog" aria-label={detail.title} onMouseDown={(e) => e.stopPropagation()} className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"><div className="flex items-start justify-between"><span className={`grid h-10 w-10 place-items-center rounded-xl ${detail.error ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}><Icon name={detail.error ? 'alert' : 'spark'} size={19}/></span><button onClick={() => setDetail(null)} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><Icon name="close" size={18}/></button></div><h3 className="mt-5 text-xl font-bold text-[#173d32]">{detail.title}</h3><p className="mt-3 max-h-[50vh] overflow-y-auto whitespace-pre-line text-sm leading-6 text-slate-500">{detail.body}</p>{!detail.error && <div className="mt-5 rounded-xl bg-[#f3f8e8] p-4 text-xs leading-5 text-[#4d6a2c]"><strong>Catatan keputusan:</strong> Evaluasi kembali setelah layanan selesai dan catat realisasi waste untuk meningkatkan akurasi model.</div>}<button onClick={() => setDetail(null)} className="mt-5 w-full rounded-xl bg-[#173d32] py-3 text-sm font-semibold text-white">Mengerti</button></article></div>}
    {notesOpen && <div className="fixed inset-0 z-[70] flex justify-end bg-slate-950/30" onMouseDown={() => setNotesOpen(false)}><aside onMouseDown={(e) => e.stopPropagation()} className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><div><p className="text-xs font-semibold text-emerald-700">NOTIFIKASI</p><h2 className="mt-1 text-xl font-bold">{unread ? `${unread} perlu perhatian` : 'Semua sudah dibaca'}</h2></div><button onClick={() => setNotesOpen(false)}><Icon name="close"/></button></div><p className="mt-2 text-xs text-slate-400">Dibuat otomatis oleh backend saat prediksi tersimpan berisiko Tinggi.</p><div className="mt-6 space-y-3">{notifications.length ? notifications.map((item) => <button key={item.id} onClick={() => readNotification(item)} className={`block w-full rounded-xl border p-4 text-left ${item.read_at ? 'border-slate-100 bg-slate-50' : 'border-orange-200 bg-orange-50'}`}><div className="flex items-start gap-3"><Icon name="alert" size={16} className={item.read_at ? 'text-slate-400' : 'text-orange-600'}/><div><p className="text-sm font-semibold">{item.title}</p><p className="mt-1 text-xs leading-5 text-slate-500">{item.message}</p><p className="mt-2 text-[10px] text-slate-400">{new Date(item.created_at).toLocaleString('id-ID')}{item.read_at ? ' · dibaca' : ' · klik untuk tandai dibaca'}</p></div></div></button>) : <p className="rounded-xl bg-slate-50 p-4 text-xs text-slate-500">Belum ada notifikasi.</p>}</div></aside></div>}
    {accountOpen && <AccountPanel user={user} settings={settings} canEdit={context.canEdit} close={() => setAccountOpen(false)} onSaved={(value) => { setSettings(value); refresh(); openDetail('Pengaturan tersimpan', `Batas Aman ${kg(value.safe_max_kg)} kg, Waspada ${kg(value.warning_max_kg)} kg, harga bahan ${rupiah(value.ingredient_cost_per_kg)}/kg, target pengurangan ${value.reduction_target_percent}%. Prediksi berikutnya memakai pengaturan ini.`) }} onError={fail} onLogout={onLogout}/>}
  </div></AppContext.Provider>
}

function AccountPanel({ user, settings, canEdit, close, onSaved, onError, onLogout }: {
  user: AppUser
  settings: Settings | null
  canEdit: boolean
  close: () => void
  onSaved: (settings: Settings) => void
  onError: (title: string, error: unknown) => void
  onLogout: () => void | Promise<void>
}) {
  const [health, setHealth] = useState<{ status: string; model?: string; detail?: string } | null>(null)
  const [form, setForm] = useState(() => settings ? {
    cost: String(settings.ingredient_cost_per_kg), safe: String(settings.safe_max_kg), warning: String(settings.warning_max_kg),
    capacity: String(settings.max_portions), target: String(settings.reduction_target_percent), email: settings.report_recipient_email ?? '', notify: settings.high_risk_notifications,
  } : null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    fetch('/health/ready').then(async (response) => setHealth(await response.json())).catch(() => setHealth({ status: 'unreachable' }))
  }, [])

  async function save() {
    if (!form) return
    setSaving(true)
    try {
      const number = (value: string) => Number(value.replace(',', '.'))
      onSaved(await updateSettings({
        ingredient_cost_per_kg: number(form.cost), safe_max_kg: number(form.safe), warning_max_kg: number(form.warning),
        max_portions: Math.round(number(form.capacity)), reduction_target_percent: number(form.target),
        high_risk_notifications: form.notify, report_recipient_email: form.email.trim() || null,
      }))
    } catch (error) {
      onError('Pengaturan belum tersimpan', error)
    } finally {
      setSaving(false)
    }
  }

  const ready = health?.status === 'ready'
  const set = (key: string) => (value: string) => setForm((current) => current && { ...current, [key]: value })
  return <div className="fixed inset-0 z-[70] flex justify-end bg-slate-950/30" onMouseDown={close}><aside onMouseDown={(e) => e.stopPropagation()} className="h-full w-full max-w-md overflow-y-auto bg-white p-6 shadow-2xl"><div className="flex items-center justify-between"><div><p className="text-xs font-semibold text-emerald-700">AKUN {(roleLabel[user.role] ?? user.role).toUpperCase()}</p><h2 className="mt-1 text-xl font-bold">{user.name}</h2></div><button onClick={close}><Icon name="close"/></button></div>
    <div className="mt-7 rounded-2xl bg-[#173d32] p-5 text-white"><div className="grid h-12 w-12 place-items-center rounded-full bg-[#ebc8a8] font-bold text-[#513a2d]">{initials(user.name)}</div><p className="mt-4 font-bold">{user.restaurantName}</p><p className="mt-1 text-xs text-white/55">{user.email}</p><span className={`mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs ${ready ? 'bg-emerald-400/15 text-emerald-200' : 'bg-orange-400/15 text-orange-200'}`}><Icon name={ready ? 'check' : 'alert'} size={14}/>{health === null ? 'Memeriksa backend...' : ready ? 'API tersambung' : 'Backend belum siap'}</span></div>
    <div className="mt-5 space-y-3 text-sm"><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Peran</span><strong>{roleLabel[user.role] ?? user.role}</strong></div><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Model aktif</span><strong>{health?.model ?? '-'}</strong></div><div className="flex justify-between rounded-xl bg-slate-50 p-4"><span className="text-slate-500">Endpoint</span><strong className={ready ? 'text-emerald-700' : 'text-amber-700'}>FastAPI /api/v1</strong></div></div>
    {!ready && health?.detail && <p className="mt-3 text-xs text-amber-700">{health.detail}</p>}
    <h3 className="mt-7 text-sm font-bold">Pengaturan restoran</h3><p className="mt-1 text-xs text-slate-400">Dipakai untuk tingkat risiko, biaya limbah, dan target di semua halaman.</p>
    {form ? <div className="mt-4 grid grid-cols-2 gap-3"><Field label="Harga bahan per kg" type="number" value={form.cost} onChange={set('cost')} suffix="Rp"/><Field label="Target pengurangan" type="number" value={form.target} onChange={set('target')} suffix="%"/><Field label="Batas Aman" type="number" step="0.1" value={form.safe} onChange={set('safe')} suffix="kg"/><Field label="Batas Waspada" type="number" step="0.1" value={form.warning} onChange={set('warning')} suffix="kg"/><Field label="Kapasitas porsi" type="number" value={form.capacity} onChange={set('capacity')}/><div className="col-span-2"><Field label="Email penerima laporan" type="email" value={form.email} onChange={set('email')} placeholder="manager@restoran.test"/></div><label className="col-span-2 flex items-center justify-between rounded-xl bg-slate-50 p-3 text-xs font-semibold text-slate-600">Notifikasi saat prediksi berisiko Tinggi<input type="checkbox" checked={form.notify} onChange={(e) => setForm({ ...form, notify: e.target.checked })} className="h-4 w-4 accent-emerald-700"/></label>{canEdit ? <button disabled={saving} onClick={save} className="col-span-2 rounded-xl border border-slate-200 py-3 text-sm font-bold disabled:opacity-60">{saving ? 'Menyimpan...' : 'Simpan Pengaturan'}</button> : <p className="col-span-2 text-xs text-slate-400">Hanya pemilik atau manager yang dapat mengubah pengaturan.</p>}</div> : <p className="mt-4 text-xs text-slate-400">Memuat pengaturan...</p>}
    <button onClick={() => void onLogout()} className="mt-6 w-full rounded-xl bg-[#173d32] py-3 text-sm font-bold text-white">Keluar dari akun</button></aside></div>
}

export default App
