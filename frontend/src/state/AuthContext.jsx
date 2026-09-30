import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../api/endpoints'
import { setAccessToken } from '../api/client'

const AuthContext = createContext(null)
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const logout = useCallback(() => { setAccessToken(null); sessionStorage.removeItem('ri_refresh_token'); setUser(null) }, [])
  const signIn = useCallback(async (email, password) => {
    // A leftover refresh token must not intercept or retry a fresh login.
    setAccessToken(null)
    sessionStorage.removeItem('ri_refresh_token')
    setUser(null)
    try {
      const { data } = await authApi.login({ email: email.trim(), password })
      setAccessToken(data.access_token)
      sessionStorage.setItem('ri_refresh_token', data.refresh_token)
      const profile = await authApi.me()
      setUser(profile.data)
      return profile.data
    } catch (error) {
      setAccessToken(null)
      sessionStorage.removeItem('ri_refresh_token')
      setUser(null)
      throw error
    }
  }, [])
  const completeFirstLogin = useCallback(async (newPassword) => {
    await authApi.firstLoginPassword({ new_password: newPassword })
    const profile = await authApi.me()
    setUser(profile.data)
    return profile.data
  }, [])
  const refreshUser = useCallback(async () => {
    if (!sessionStorage.getItem('ri_refresh_token')) { setLoading(false); return }
    try { const { data } = await authApi.me(); setUser(data) } catch { logout() } finally { setLoading(false) }
  }, [logout])
  useEffect(() => { refreshUser(); const expire = () => logout(); window.addEventListener('ri:session-expired', expire); return () => window.removeEventListener('ri:session-expired', expire) }, [refreshUser, logout])
  const value = useMemo(() => ({ user, loading, signIn, completeFirstLogin, logout, refreshUser }), [user, loading, signIn, completeFirstLogin, logout, refreshUser])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
export const useAuth = () => useContext(AuthContext)
