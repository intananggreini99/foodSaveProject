'use client'

import { useEffect, useRef, useState } from 'react'
import {
  allOperations, createOperation, getCorrections, getScenarioOptions, listOperations, predictOperation, previewPrediction,
  updateOperation, uploadImport,
  type DailyOperation, type DataImport, type Prediction, type ScenarioOptions,
} from '@/lib/api'
import {
  CATEGORIES, addDays, downloadText, experienceLabel, fromForm, kg, mediumDate, num, percent, planFrom, riskLabel,
  riskOf, rupiah, sampleCsv, shortDate, toForm, withActual, type DailyForm,
} from '@/lib/format'
import { errorText, useApp } from './context'
import { bestOption } from './Overview'
import { Empty, Field, Icon, selectClass } from './ui'

export default function InputHarian() {
  const { today, version, settings, focusDate, clearFocus, openDetail, fail, refresh, canEdit } = useApp()
  const [inputTab, setInputTab] = useState('manual')
  const [date, setDate] = useState(focusDate ?? today)
  const [form, setForm] = useState<DailyForm | null>(null)
  const [existing, setExisting] = useState<DailyOperation | null>(null)
  const [reason, setReason] = useState('')
  const [yesterday, setYesterday] = useState<DailyOperation | null>(null)
  const [options, setOptions] = useState<ScenarioOptions | null>(null)
  const [recent, setRecent] = useState<DailyOperation[]>([])
  const [history, setHistory] = useState<DailyOperation[] | null>(null)
  const [preview, setPreview] = useState<{ result: Prediction | null; error: string | null; loading: boolean }>({ result: null, error: null, loading: false })
  const [saving, setSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => { if (focusDate) { setDate(focusDate); setInputTab('manual'); clearFocus() } }, [focusDate, clearFocus])

  // Riwayat singkat dan kelengkapan 90 hari.
  useEffect(() => {
    listOperations({ limit: 5 }).then((page) => setRecent(page.items)).catch((error) => fail('Input terakhir belum dapat dimuat', error))
    allOperations(addDays(today, -89), today).then(setHistory).catch(() => setHistory([]))
  }, [today, version, fail])

  // Muat data tanggal terpilih (ubah) atau siapkan isian baru.
  useEffect(() => {
    let alive = true
    Promise.all([
      listOperations({ starts_on: date, ends_on: date, limit: 1 }),
      listOperations({ starts_on: addDays(date, -1), ends_on: addDays(date, -1), limit: 1 }),
      listOperations({ ends_on: addDays(date, -1), limit: 1 }),
    ]).then(([current, previousDay, latest]) => {
      if (!alive) return
      const row = current.items[0] ?? null
      const before = previousDay.items[0] ?? null
      setExisting(row)
      setYesterday(before)
      setReason('')
      setForm(row ? toForm(row) : toForm(planFrom(latest.items[0] ?? null, date, num(before?.actual_waste_kg))))
      setOptions(null)
      if (row) getScenarioOptions(row.id, null).then((value) => alive && setOptions(value)).catch(() => undefined)
    }).catch((error) => fail('Data tanggal ini belum dapat dimuat', error))
    return () => { alive = false }
  }, [date, version, reloadKey, fail])

  // Pratinjau langsung (tidak menyimpan) setiap isian rencana berubah.
  const planKey = form ? [form.operation_date, form.meals_prepared, form.kitchen_staff, form.staff_experience, form.special_event, form.temperature_c, form.humidity_percent].join('|') : ''
  useEffect(() => {
    if (!form) return
    const fields = fromForm(form)
    if (!(fields.meals_prepared >= 0) || !(fields.kitchen_staff > 0) || Number.isNaN(fields.temperature_c) || Number.isNaN(fields.humidity_percent)) {
      setPreview({ result: null, error: 'Lengkapi porsi, staf, suhu, dan kelembapan untuk melihat pratinjau.', loading: false })
      return
    }
    setPreview((current) => ({ ...current, loading: true }))
    const timer = window.setTimeout(() => {
      previewPrediction({
        operation_date: fields.operation_date, meals_prepared: fields.meals_prepared, kitchen_staff: fields.kitchen_staff,
        staff_experience: fields.staff_experience, special_event: fields.special_event, temperature_c: fields.temperature_c, humidity_percent: fields.humidity_percent,
      })
        .then((result) => setPreview({ result, error: null, loading: false }))
        .catch((error) => setPreview({ result: null, error: errorText(error), loading: false }))
    }, 400)
    return () => window.clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planKey])

  const set = (key: keyof DailyForm) => (value: string | boolean) => setForm((current) => current && { ...current, [key]: value })

  function changeDate(value: string) {
    if (value) setDate(value)
  }

  async function save() {
    if (!form) return
    if (existing && reason.trim().length < 3) {
      openDetail('Alasan perubahan diperlukan', 'Tanggal ini sudah memiliki data. Tulis alasan perubahan (minimal 3 karakter) agar koreksi tercatat di riwayat.')
      return
    }
    setSaving(true)
    try {
      const fields = fromForm(form)
      const row = existing
        ? await updateOperation(existing.id, { ...fields, expected_version: existing.version, correction_reason: reason.trim() })
        : await createOperation(fields)
      const result = await predictOperation(row.id)
      openDetail(existing ? 'Perubahan tersimpan' : 'Data tersimpan', `Rencana ${mediumDate(row.operation_date)} (${row.meals_prepared} porsi, ${row.kitchen_staff} staf) tersimpan. Prediksi limbah ${kg(result.predicted_waste_kg)} kg, risiko ${riskLabel[result.risk_level]}, perkiraan biaya ${rupiah(result.estimated_waste_cost)}.`)
      refresh()
    } catch (error) {
      fail('Data belum tersimpan', error)
    } finally {
      setSaving(false)
    }
  }

  async function showCorrections(row: DailyOperation) {
    try {
      const items = await getCorrections(row.id)
      const body = items.length
        ? items.map((item) => {
          const same = (a: unknown, b: unknown) => (a !== null && b !== null && a !== '' && b !== '' && !Number.isNaN(Number(a)) && !Number.isNaN(Number(b)) && typeof a !== 'boolean' ? Number(a) === Number(b) : JSON.stringify(a ?? null) === JSON.stringify(b ?? null))
          const changed = Object.keys(item.new_values).filter((key) => !same(item.new_values[key as keyof typeof item.new_values], item.previous_values[key as keyof typeof item.previous_values]))
          return `• ${new Date(item.created_at).toLocaleString('id-ID')}: ${item.reason}${changed.length ? ` (${changed.join(', ')})` : ''}`
        }).join('\n')
        : 'Belum ada perubahan sejak data pertama kali disimpan.'
      openDetail(`Riwayat perubahan ${mediumDate(row.operation_date)}`, body)
    } catch (error) {
      fail('Riwayat belum dapat dimuat', error)
    }
  }

  const fields = form ? fromForm(form) : null
  const load = fields && fields.kitchen_staff > 0 ? fields.meals_prepared / fields.kitchen_staff : null
  const result = preview.result
  const risk = result ? riskLabel[result.risk_level] : null
  const yesterdayWaste = num(yesterday?.actual_waste_kg)
  const best = bestOption(options)
  const dateLabel = date === today ? 'hari ini' : `untuk ${shortDate(date)}`
  const riskPhrase = risk === 'Aman' ? 'masih aman' : risk === 'Waspada' ? 'perlu diwaspadai' : risk === 'Tinggi' ? 'berisiko tinggi' : ''
  const cards: Array<[string, string, string, boolean]> = [
    ['Beban staf', load === null ? '-' : `${Math.round(load)} porsi/orang`, load !== null && load > 35 ? `Butuh ${Math.ceil((fields?.meals_prepared ?? 0) / 35)} staf agar beban ≤35 porsi.` : 'Beban masih di bawah 35 porsi per staf.', load !== null && load > 35],
    ['Limbah kemarin', yesterdayWaste === null ? '-' : `${kg(yesterdayWaste)} kg`, yesterdayWaste === null ? `Belum dicatat untuk ${shortDate(addDays(date, -1))}.` : `Risiko ${riskOf(yesterdayWaste, settings) ?? '-'} menurut batas restoran.`, riskOf(yesterdayWaste, settings) === 'Tinggi'],
    ['Potensi hemat', best ? rupiah(best.savings_amount) : existing && options ? 'Rp0' : '-', best ? `Pakai saran ${best.simulated_portions} porsi.` : existing ? 'Pengurangan porsi belum menurunkan limbah.' : 'Simpan rencana untuk melihat saran porsi.', false],
  ]
  const total = history?.length ?? 0
  const missing = (history ?? []).filter((row) => row.actual_waste_kg === null && row.operation_date < today)
  const complete = total ? (withActual(history ?? []).length / total) * 100 : 0

  return <div className="page-enter">
    <div className="mb-7"><h1 className="text-2xl font-bold sm:text-[30px]">{fields ? `Rencana ${fields.meals_prepared} porsi ${dateLabel} ${riskPhrase}`.trim() : 'Memuat rencana...'}</h1><p className="mt-1 text-sm text-slate-500">{existing ? `Data ${mediumDate(date)} sudah tersimpan (versi ${existing.version}); perubahan dicatat sebagai koreksi.` : 'Isi kondisi dapur, lalu lihat perkiraan limbah secara langsung.'}</p></div>
    <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">{cards.map(([title, value, note, warn]) => <article className={`rounded-xl border p-4 ${warn ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`} key={title}><Icon name={warn ? 'alert' : 'leaf'} size={17}/><p className="mt-2 text-xs font-semibold">{title}</p><strong className="mt-1 block text-lg">{value}</strong><p className="mt-1 text-[10px] text-slate-500">{note}</p></article>)}</div>
    <div className="mb-4 inline-flex rounded-xl bg-slate-200/60 p-1">{[['manual', 'Input Manual'], ['file', 'Unggah File (CSV/Excel)']].map(([v, l]) => <button key={v} onClick={() => setInputTab(v)} className={`rounded-lg px-4 py-2 text-xs font-semibold ${inputTab === v ? 'bg-white text-[#173d32] shadow-sm' : 'text-slate-500'}`}>{l}</button>)}</div>
    {inputTab === 'file' ? <UploadPanel /> : !form ? <article className="card text-sm text-slate-500">Memuat data...</article> :
    <div className="grid gap-4 xl:grid-cols-[1.35fr_.65fr]">
      <article className="card"><h2 className="section-title">Kondisi Operasional</h2><p className="section-subtitle">{existing ? `Mengubah data ${mediumDate(date)}` : `Rencana operasional ${date === today ? 'hari ini' : mediumDate(date)}`}</p><div className="mt-6 grid gap-5 sm:grid-cols-2">
        <Field label="Tanggal" type="date" value={date} onChange={changeDate}/>
        <Field label="Jumlah porsi disiapkan" type="number" min="0" value={form.meals_prepared} onChange={set('meals_prepared')}/>
        <Field label="Jumlah staf dapur" type="number" min="1" value={form.kitchen_staff} onChange={set('kitchen_staff')}/>
        <label><span className="mb-2 block text-xs font-semibold text-slate-600">Pengalaman staf</span><select value={form.staff_experience} onChange={(e) => set('staff_experience')(e.target.value)} className={selectClass}>{(['expert', 'intermediate', 'beginner'] as const).map((level) => <option key={level} value={level}>{experienceLabel[level]}</option>)}</select></label>
        <Field label="Suhu dapur" type="number" step="0.1" value={form.temperature_c} onChange={set('temperature_c')} suffix="°C"/>
        <Field label="Kelembapan" type="number" step="0.1" min="0" max="100" value={form.humidity_percent} onChange={set('humidity_percent')} suffix="%"/>
        <Field label="Limbah kemarin (otomatis)" type="number" step="0.01" min="0" value={form.previous_waste_kg} onChange={set('previous_waste_kg')} suffix="kg" placeholder="Belum dicatat"/>
        <label><span className="mb-2 block text-xs font-semibold text-slate-600">Kategori utama</span><select value={form.waste_category} onChange={(e) => set('waste_category')(e.target.value)} className={selectClass}><option value="">Belum dipilih</option>{CATEGORIES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}{form.waste_category && !CATEGORIES.some(([value]) => value === form.waste_category) && <option value={form.waste_category}>{form.waste_category}</option>}</select></label>
        <label className="flex items-center justify-between self-end rounded-xl bg-slate-50 p-3"><span className="text-xs font-semibold text-slate-600">Ada acara khusus</span><input type="checkbox" checked={form.special_event} onChange={(e) => set('special_event')(e.target.checked)} className="h-4 w-4 accent-emerald-700"/></label>
        <Field label="Limbah aktual (isi setelah ditimbang)" type="number" step="0.01" min="0" value={form.actual_waste_kg} onChange={set('actual_waste_kg')} suffix="kg" placeholder="Belum ditimbang"/>
        {form.special_event && <div className="sm:col-span-2"><Field label="Jenis acara (opsional)" value={form.event_type} onChange={set('event_type')} placeholder="Contoh: Reservasi rombongan"/></div>}
        <label className="sm:col-span-2"><span className="mb-2 block text-xs font-semibold text-slate-600">Catatan</span><textarea value={form.manager_notes} onChange={(e) => set('manager_notes')(e.target.value)} placeholder="Contoh: Reservasi rombongan 24 orang pukul 19.00" className="w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm"/></label>
        {existing && <div className="sm:col-span-2"><Field label="Alasan perubahan (wajib saat mengubah data)" value={reason} onChange={setReason} placeholder="Contoh: Penimbangan limbah aktual selesai"/></div>}
      </div><div className="mt-5 flex gap-3"><button disabled={saving || !canEdit} onClick={save} className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-[#173d32] py-3 text-sm font-semibold text-white disabled:opacity-60"><Icon name="check" size={17}/>{saving ? 'Menyimpan...' : existing ? 'Simpan Perubahan & Prediksi' : 'Simpan & Prediksi'}</button><button onClick={() => setReloadKey((key) => key + 1)} className="rounded-xl border border-slate-200 px-5 text-sm font-semibold">Reset</button></div>{!canEdit && <p className="mt-3 text-xs text-slate-400">Peran staf hanya dapat melihat data.</p>}</article>
      <article className="card bg-[#173d32] text-white"><p className="text-xs font-semibold text-emerald-100/65">PRATINJAU LANGSUNG</p>{result ? <><div className={`mt-8 text-center transition-opacity ${preview.loading ? 'opacity-60' : ''}`}><strong className="text-6xl">{kg(result.predicted_waste_kg)}</strong><span className="ml-2 text-lg text-white/60">kg</span><p className="mt-3 text-sm text-white/55">Sekitar {rupiah(result.estimated_waste_cost)} · rentang {kg(result.interval_lower_kg)}–{kg(result.interval_upper_kg)} kg</p><span className={`mt-6 inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ${risk === 'Aman' ? 'bg-emerald-400/15 text-emerald-300' : risk === 'Tinggi' ? 'bg-red-400/15 text-red-300' : 'bg-orange-400/15 text-orange-300'}`}><Icon name={risk === 'Aman' ? 'check' : 'alert'} size={16}/>{risk}</span></div><div className="mt-7 rounded-xl bg-white/8 p-4 text-xs leading-5 text-white/65">Beban {Math.round(Number(result.portions_per_staff))} porsi per staf — {Number(result.portions_per_staff) > 35 ? 'Berat' : 'Normal'}. Kurangi porsi atau tambah staf bila beban melewati 35.{result.outside_training_range && ` Perhatian: ${result.outside_fields?.join(', ')} di luar rentang data latih model, hasil kurang pasti.`}</div></>
        : <div className="mt-8 rounded-xl bg-white/8 p-4 text-sm leading-6 text-white/70">{preview.loading ? 'Menghitung pratinjau...' : preview.error}</div>}<p className="mt-4 text-[10px] text-white/40">Pratinjau tidak disimpan. Prediksi tersimpan saat menekan Simpan & Prediksi.</p></article>
    </div>}
    <div className="mt-4 grid gap-4 lg:grid-cols-[1.3fr_.7fr]"><article className="card overflow-x-auto"><h2 className="section-title">5 Input Terakhir</h2>{recent.length ? <table className="mt-4 w-full min-w-[520px] text-left text-xs"><thead><tr className="text-slate-400">{['Tanggal', 'Porsi', 'Staf', 'Limbah', 'Aksi'].map((x) => <th className="pb-3" key={x}>{x}</th>)}</tr></thead><tbody>{recent.map((row) => <tr className="border-t border-slate-100" key={row.id}><td className="py-3">{shortDate(row.operation_date)}</td><td className="py-3">{row.meals_prepared}</td><td className="py-3">{row.kitchen_staff}</td><td className="py-3">{row.actual_waste_kg === null ? 'Belum ditimbang' : `${kg(row.actual_waste_kg)} kg`}</td><td><button onClick={() => { setInputTab('manual'); setDate(row.operation_date); window.scrollTo({ top: 0, behavior: 'smooth' }) }} className="text-emerald-700">Edit</button> · <button onClick={() => showCorrections(row)} className="text-slate-500">Riwayat</button></td></tr>)}</tbody></table> : <div className="mt-4"><Empty>Belum ada data harian. Isi form di atas atau unggah file CSV/Excel.</Empty></div>}</article><article className="card"><span className="metric-icon green"><Icon name="check"/></span><h3 className="mt-4 font-bold">Data siap dipakai</h3><strong className="mt-2 block text-3xl text-[#173d32]">{history === null ? '...' : total ? `${percent(complete)} lengkap` : '0 hari'}</strong><p className="mt-2 text-xs leading-5 text-slate-500">{total ? `${withActual(history ?? []).length} dari ${total} hari dalam 90 hari terakhir sudah punya limbah aktual. Limbah aktual dipakai untuk mengukur akurasi dan melatih ulang model.` : 'Belum ada data harian dalam 90 hari terakhir.'}</p><button onClick={() => openDetail(missing.length ? 'Limbah aktual belum dicatat' : 'Data lengkap', missing.length ? `${missing.slice(0, 15).map((row) => `• ${mediumDate(row.operation_date)}`).join('\n')}${missing.length > 15 ? `\n… dan ${missing.length - 15} tanggal lain` : ''}\n\nPilih tanggal di form, isi limbah aktual, lalu simpan.` : 'Semua hari yang sudah lewat memiliki limbah aktual.')} className="mt-4 text-xs font-bold text-emerald-700">Lihat yang belum lengkap</button></article></div>
  </div>
}

function UploadPanel() {
  const { today, openDetail, fail, refresh, canEdit } = useApp()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [check, setCheck] = useState<DataImport | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [predict, setPredict] = useState(true)

  async function choose(selected: File | undefined) {
    if (!selected) return
    setFile(selected)
    setCheck(null)
    setBusy('Memeriksa file...')
    try {
      setCheck(await uploadImport(selected, false))
    } catch (error) {
      fail('File belum dapat diperiksa', error)
      setFile(null)
    } finally {
      setBusy(null)
      if (input.current) input.current.value = ''
    }
  }

  async function apply() {
    if (!file) return
    setBusy('Menyimpan baris...')
    try {
      const record = await uploadImport(file, true)
      let predicted = 0
      let failed = 0
      if (predict && record.applied_rows) {
        const rows = (await allOperations('1900-01-01', '2999-12-31')).filter((row) => row.import_id === record.id)
        for (const row of rows) {
          setBusy(`Menjalankan prediksi ${predicted + failed + 1}/${rows.length}...`)
          try { await predictOperation(row.id); predicted += 1 } catch { failed += 1 }
        }
      }
      openDetail('File tersimpan', `${record.applied_rows} baris dari ${record.file_name} tersimpan sebagai input harian.${predict ? ` Prediksi dibuat untuk ${predicted} tanggal${failed ? `, ${failed} gagal` : ''}.` : ''}${record.invalid_rows ? ` ${record.invalid_rows} baris tidak valid dilewati.` : ''}`)
      setFile(null)
      setCheck(null)
      refresh()
    } catch (error) {
      fail('File belum tersimpan', error)
    } finally {
      setBusy(null)
    }
  }

  return <article className="card mb-4 grid min-h-72 place-items-center border-dashed text-center"><div className="w-full max-w-xl">
    <Icon name="database" size={38} className="mx-auto text-[#2d826b]"/>
    <h2 className="mt-4 font-bold">Unggah catatan operasional</h2>
    <p className="mt-2 text-sm text-slate-400">CSV UTF-8 atau Excel .xlsx, maksimal 5 MB. Satu baris per tanggal; tanggal yang sudah ada dilewati.</p>
    <input ref={input} type="file" accept=".csv,.xlsx" className="hidden" onChange={(event) => choose(event.target.files?.[0])}/>
    {!check && <div className="mt-5 flex flex-wrap justify-center gap-3"><button disabled={Boolean(busy) || !canEdit} onClick={() => input.current?.click()} className="rounded-xl bg-[#173d32] px-5 py-3 text-sm font-semibold text-white disabled:opacity-60">{busy ?? 'Pilih file'}</button><button onClick={() => downloadText(sampleCsv(today), `contoh_input_harian_${today}.csv`)} className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold">Unduh contoh CSV (30 hari)</button></div>}
    {check && <div className="mt-5 rounded-xl bg-slate-50 p-4 text-left text-xs leading-5 text-slate-600">
      <p><strong>{check.file_name}</strong>: {check.total_rows} baris ditemukan. <strong className="text-emerald-700">{check.valid_rows} siap disimpan</strong>, {check.invalid_rows} tidak valid, {check.unusual_rows} perlu diperiksa.</p>
      {check.validation_results.length > 0 && <ul className="mt-3 max-h-40 space-y-1 overflow-y-auto">{check.validation_results.slice(0, 20).map((item) => <li key={`${item.row}-${item.status}`} className={item.status === 'invalid' ? 'text-red-600' : 'text-amber-700'}>Baris {item.row}: {item.messages.join('; ')}</li>)}</ul>}
      <label className="mt-3 flex items-center gap-2"><input type="checkbox" checked={predict} onChange={(event) => setPredict(event.target.checked)} className="accent-emerald-700"/>Jalankan prediksi untuk setiap tanggal yang disimpan</label>
      <div className="mt-4 flex gap-2"><button disabled={Boolean(busy) || !check.valid_rows} onClick={apply} className="rounded-xl bg-[#173d32] px-4 py-2.5 text-xs font-semibold text-white disabled:opacity-60">{busy ?? `Simpan ${check.valid_rows} baris`}</button><button disabled={Boolean(busy)} onClick={() => { setCheck(null); setFile(null) }} className="rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold">Batal</button></div>
    </div>}
  </div></article>
}
