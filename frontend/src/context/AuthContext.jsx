import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { get, patch, post } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [showSplash, setShowSplash] = useState(false)
  const [loading, setLoading] = useState(true)
  const [twoFactorRequired, setTwoFactorRequired] = useState(false)

  const loadUser = useCallback(async ({ preserveOnError = false } = {}) => {
    try { const current = await get('/accounts/me/'); setUser(current); return current } catch (error) { if (!preserveOnError || error.status === 401 || error.status === 403) setUser(null); return null } finally { setLoading(false) }
  }, [])
  const refreshUser = useCallback(() => loadUser({ preserveOnError: true }), [loadUser])
  useEffect(() => { loadUser() }, [loadUser])

  // Inactivity auto-logout timer (30 minutes = 1,800,000 ms)
  useEffect(() => {
    if (!user) return undefined

    let inactivityTimer
    const resetTimer = () => {
      if (inactivityTimer) clearTimeout(inactivityTimer)
      inactivityTimer = setTimeout(() => {
        post('/accounts/auth/logout/').finally(() => {
          setUser(null)
          alert('Your session has timed out due to 30 minutes of inactivity. Please log in again.')
        })
      }, 30 * 60 * 1000)
    }

    const events = ['mousemove', 'keydown', 'scroll', 'click', 'touchstart']
    events.forEach((evt) => window.addEventListener(evt, resetTimer))
    resetTimer()

    const refreshVisibleUser = () => {
      if (document.visibilityState === 'visible') refreshUser()
    }
    window.addEventListener('focus', refreshVisibleUser)
    window.addEventListener('auth-role-refresh', refreshVisibleUser)
    document.addEventListener('visibilitychange', refreshVisibleUser)
    const interval = window.setInterval(refreshVisibleUser, 30000)

    return () => {
      if (inactivityTimer) clearTimeout(inactivityTimer)
      events.forEach((evt) => window.removeEventListener(evt, resetTimer))
      window.removeEventListener('focus', refreshVisibleUser)
      window.removeEventListener('auth-role-refresh', refreshVisibleUser)
      document.removeEventListener('visibilitychange', refreshVisibleUser)
      window.clearInterval(interval)
    }
  }, [user?.id, refreshUser])

  const login = async (email, password) => {
    const result = await post('/accounts/auth/login/', { email, password })
    if (result.two_factor_required) { setTwoFactorRequired(true); return result }
    const currentUser = await loadUser()
    setShowSplash(true)
    window.setTimeout(() => setShowSplash(false), 900)
    return { ...result, user: currentUser }
  }

  const signup = async (fields) => {
    return post('/accounts/auth/register/', fields)
  }

  const logout = async () => { try { await post('/accounts/auth/logout/') } finally { setUser(null) } }

  const becomeSeller = () => {}

  const updateProfile = async (fields) => { const next = await patch('/accounts/me/', fields); setUser(next); return next }

  return (
    <AuthContext.Provider
      value={{ user, login, signup, logout, becomeSeller, updateProfile, refreshUser, showSplash, loading, twoFactorRequired }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
