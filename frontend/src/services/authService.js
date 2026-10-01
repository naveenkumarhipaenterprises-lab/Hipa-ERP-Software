import { authApi } from '../api/authApi'
import { tokenStorage } from '../api/client'

export const authService = {
  getCurrentUser: () => (tokenStorage.get() ? tokenStorage.getUser() : null),

  async login({ username, password, remember }) {
    const { access, user } = await authApi.login(username.trim(), password)
    if (!access || !user) throw new Error('Unexpected response from the server. Please contact your administrator.')
    tokenStorage.set(access, user, remember)
    return user
  },

  /** Always ends the local session, even if the server call fails. */
  async logout() {
    try {
      await authApi.logout()
    } finally {
      tokenStorage.clear()
    }
  },

  forgotPassword: (email) => authApi.forgotPassword(email),
  resetPassword: (token, password, uid) => authApi.resetPassword(token, password, uid),
}
