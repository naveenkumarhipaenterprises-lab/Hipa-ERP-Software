import { render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { tokenStorage } from '../api/client'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'

/**
 * Renders UI inside the same providers the app uses.
 * `role` signs in a test user with that role first (stored like a real session).
 */
export function renderWithApp(ui, { route = '/', role } = {}) {
  if (role) tokenStorage.set('test-token', { id: 1, name: 'Test User', email: 'test@example.com', role }, false)
  const user = userEvent.setup()
  const result = render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <ToastProvider>{ui}</ToastProvider>
      </AuthProvider>
    </MemoryRouter>,
  )
  return { user, ...result }
}
