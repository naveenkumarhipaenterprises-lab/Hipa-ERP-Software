import { screen } from '@testing-library/react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { renderWithApp } from '../test/render'
import ProtectedRoute from './ProtectedRoute'

function LoginProbe() {
  const { state } = useLocation()
  return <p>Login page (from {state?.from})</p>
}

const app = (
  <Routes>
    <Route path="/login" element={<LoginProbe />} />
    <Route path="/finance" element={<ProtectedRoute module="finance">Finance content</ProtectedRoute>} />
  </Routes>
)

describe('ProtectedRoute', () => {
  it('sends signed-out visitors to login, remembering where they were going', () => {
    renderWithApp(app, { route: '/finance?range=this_month' })
    expect(screen.getByText('Login page (from /finance?range=this_month)')).toBeInTheDocument()
  })

  it('blocks roles without access to the module', () => {
    renderWithApp(app, { route: '/finance', role: 'sales' })
    expect(screen.getByText("You don't have access to this module")).toBeInTheDocument()
    expect(screen.queryByText('Finance content')).not.toBeInTheDocument()
  })

  it('lets allowed roles in', () => {
    renderWithApp(app, { route: '/finance', role: 'finance' })
    expect(screen.getByText('Finance content')).toBeInTheDocument()
  })
})
