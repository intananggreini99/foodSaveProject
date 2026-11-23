'use client'

import { FormEvent, useState } from 'react'
import { login, register } from '@/lib/api'

type ApiUser = Awaited<ReturnType<typeof login>>

export default function AuthScreen({
  onAuthenticated,
  onDemo,
}: {
  onAuthenticated: (user: ApiUser) => void
  onDemo: () => void
}) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    setPending(true)
    setMessage('')
    try {
      const user = mode === 'login'
        ? await login(String(form.get('email')), String(form.get('password')))
        : await register({
            name: String(form.get('name')),
            restaurantName: String(form.get('restaurantName')),
            email: String(form.get('email')),
            password: String(form.get('password')),
          })
      onAuthenticated(user)
    } catch {
      setMessage('Akun atau data belum dapat diproses. Periksa koneksi backend dan isian form.')
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="grid min-h-screen bg-[#f5f7f4] lg:grid-cols-2">
      <section className="hidden bg-[#12342b] p-14 text-white lg:flex lg:flex-col">
        <div className="flex items-center gap-3 text-xl font-bold"><span className="grid h-11 w-11 place-items-center rounded-xl bg-[#c7ef5d] text-[#17352c]">FS</span>FoodSave Restaurant</div>
        <div className="my-auto max-w-xl"><p className="text-sm font-semibold uppercase tracking-[.22em] text-[#c7ef5d]">Ruang kerja manager</p><h1 className="mt-5 text-5xl font-bold leading-tight">Kurangi limbah, jaga biaya tetap sehat.</h1><p className="mt-6 max-w-md leading-7 text-emerald-50/60">Pantau kondisi dapur, rencanakan porsi, dan bagikan laporan dalam satu tempat.</p></div>
        <p className="text-xs text-white/35">Akses khusus manager restoran</p>
      </section>
      <section className="flex items-center justify-center p-5 sm:p-10">
        <div className="w-full max-w-md rounded-3xl bg-white p-7 shadow-xl shadow-emerald-950/5 sm:p-10">
          <p className="text-sm font-semibold text-[#2d826b]">{mode === 'login' ? 'Selamat datang kembali' : 'Buat akun manager'}</p>
          <h2 className="mt-2 text-3xl font-bold text-[#173d32]">{mode === 'login' ? 'Masuk ke Overview' : 'Mulai kelola restoran'}</h2>
          <form onSubmit={submit} className="mt-8 space-y-4">
            {mode === 'register' && <><AuthField name="name" label="Nama manager" /><AuthField name="restaurantName" label="Nama restoran" /></>}
            <AuthField name="email" label="Email" type="email" />
            <AuthField name="password" label="Kata sandi" type="password" />
            {message && <p className="rounded-xl bg-red-50 px-4 py-3 text-xs text-red-700">{message}</p>}
            <button disabled={pending} className="w-full rounded-xl bg-[#173d32] py-3.5 text-sm font-bold text-white disabled:opacity-60">{pending ? 'Memproses...' : mode === 'login' ? 'Masuk' : 'Buat Akun & Masuk'}</button>
          </form>
          <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setMessage('') }} className="mt-6 w-full text-center text-xs font-semibold text-[#2d826b]">{mode === 'login' ? 'Belum punya akun? Buat akun manager' : 'Sudah punya akun? Masuk'}</button>
          <button type="button" onClick={onDemo} className="mt-4 w-full rounded-xl border border-slate-200 py-3 text-xs font-semibold text-slate-500">Buka demo frontend</button>
        </div>
      </section>
    </main>
  )
}

function AuthField({ name, label, type = 'text' }: { name: string; label: string; type?: string }) {
  return <label className="block"><span className="mb-2 block text-xs font-semibold text-slate-600">{label}</span><input name={name} type={type} required minLength={type === 'password' ? 10 : undefined} className="w-full rounded-xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-emerald-600" /></label>
}
