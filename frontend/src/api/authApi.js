import { api } from './client'

/**
 * Authentication endpoints (Django REST API).
 * Expected login response: { access, refresh?, user: { id, name, email, role } }
 */
export const authApi = {
  login: (username, password) => api.post('/auth/login/', { username, password }),
  logout: () => api.post('/auth/logout/'),
  forgotPassword: (email) => api.post('/auth/password/forgot/', { email }),
  // `uid` comes from Django-style reset links (?uid=...&token=...) and is sent only when present
  resetPassword: (token, password, uid) =>
    api.post('/auth/password/reset/', uid ? { uid, token, password } : { token, password }),
}
