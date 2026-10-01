import { describe, expect, it } from 'vitest'
import { safeRedirect } from './redirect'

describe('safeRedirect (where to go after login)', () => {
  it('keeps same-app paths, including their query', () => {
    expect(safeRedirect('/sales?tab=orders')).toBe('/sales?tab=orders')
  })
  it('refuses links to other sites', () => {
    expect(safeRedirect('//evil.example')).toBe('/dashboard')
    expect(safeRedirect('https://evil.example')).toBe('/dashboard')
  })
  it('never sends you back to a login page', () => {
    expect(safeRedirect('/login')).toBe('/dashboard')
    expect(safeRedirect('/reset-password?token=x')).toBe('/dashboard')
  })
  it('falls back to the dashboard when nothing is given', () => {
    expect(safeRedirect(undefined)).toBe('/dashboard')
  })
})
