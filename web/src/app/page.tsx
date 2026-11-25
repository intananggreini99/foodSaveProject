'use client'

import { useCallback, useEffect, useState } from 'react'
import AuthScreen from './AuthScreen'
import FoodSaveApp, { type AppUser } from './FoodSaveApp'
import { ApiError, getMe, getRestaurant, logout, setUnauthorizedHandler, type ApiUser } from '@/lib/api'

async function appUserFrom(user: ApiUser): Promise<AppUser> {
  const restaurant = await getRestaurant().catch(() => undefined)
  return { id: String(user.id), email: user.email, name: user.name, role: user.role, restaurantName: restaurant?.name ?? 'Restoran FoodSave' }
}

export default function HomePage() {
  const [user, setUser] = useState<AppUser | null>(null)
  const [checking, setChecking] = useState(true)
  const [notice, setNotice] = useState('')

  const signOut = useCallback((message = '') => { setUser(null); setNotice(message) }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => signOut('Sesi berakhir. Silakan masuk kembali.'))
    getMe()
      .then(async (current) => setUser(await appUserFrom(current)))
      .catch((error) => { if (!(error instanceof ApiError && error.status === 401)) setNotice(error.message) })
      .finally(() => setChecking(false))
    return () => setUnauthorizedHandler(null)
  }, [signOut])

  if (checking) return <div className="grid min-h-screen place-items-center bg-[#f5f7f4] text-sm text-slate-500">Memeriksa sesi...</div>
  if (!user) return <AuthScreen notice={notice} onAuthenticated={async (next) => { setNotice(''); setUser(await appUserFrom(next)) }} />
  return <FoodSaveApp user={user} onLogout={async () => { await logout().catch(() => undefined); signOut() }} />
}
