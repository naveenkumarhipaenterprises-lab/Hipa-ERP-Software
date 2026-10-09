import { useCallback, useEffect, useMemo, useState } from 'react'
import { authService } from '../services/authService'
import { canAccess, userRoles } from '../utils/constants'
import { AuthContext } from './contexts'

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => authService.getCurrentUser())
  // True after the backend rejected a stored session, so the login page can say why
  const [sessionExpired, setSessionExpired] = useState(false)

  const login = useCallback(async (credentials) => {
    const u = await authService.login(credentials)
    setSessionExpired(false)
    setUser(u)
    return u
  }, [])

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } finally {
      setSessionExpired(false)
      setUser(null)
    }
  }, [])

  // The API client fires this when the backend rejects the token (401)
  useEffect(() => {
    const onExpired = () => {
      setSessionExpired(true)
      setUser(null)
    }
    window.addEventListener('auth:logout', onExpired)
    return () => window.removeEventListener('auth:logout', onExpired)
  }, [])

  const value = useMemo(
    () => ({
      user,
      isAuthenticated: Boolean(user),
      sessionExpired,
      login,
      logout,
      can: (moduleKey) => (user ? canAccess(userRoles(user), moduleKey) : false),
    }),
    [user, sessionExpired, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
