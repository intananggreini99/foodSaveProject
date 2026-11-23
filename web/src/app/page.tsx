'use client'

import { useEffect, useState } from 'react'
import AuthScreen from './AuthScreen'
import FoodSaveApp, { type AppUser } from './FoodSaveApp'
import { getMe, getRestaurant, hasApiUrl, logout, toAppUser } from '@/lib/api'

const demoUser: AppUser = {
  id: 'demo',
  email: 'manager@foodsave.id',
  name: 'Alya Rahma',
  restaurantName: 'FoodSave Restaurant',
}

export default function HomePage() {
  const [user, setUser] = useState<AppUser | null>(hasApiUrl ? null : demoUser)
  const [checkingSession, setCheckingSession] = useState(hasApiUrl)

  async function appUserFromApi(currentUser: Awaited<ReturnType<typeof getMe>>) {
    const restaurant = await getRestaurant().catch(() => undefined)
    return toAppUser(currentUser, restaurant?.name)
  }

  useEffect(() => {
    if (!hasApiUrl) return
    getMe()
      .then(async (currentUser) => setUser(await appUserFromApi(currentUser)))
      .catch(() => setUser(null))
      .finally(() => setCheckingSession(false))
  }, [])

  if (checkingSession) return <div className="grid min-h-screen place-items-center bg-[#f5f7f4] text-sm text-slate-500">Memeriksa sesi...</div>
  if (!user) return <AuthScreen onAuthenticated={async (nextUser) => setUser(await appUserFromApi(nextUser))} onDemo={() => setUser(demoUser)} />
  return <FoodSaveApp user={user} onLogout={hasApiUrl ? async () => { await logout().catch(() => undefined); setUser(null) } : undefined} />
}
