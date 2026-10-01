import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const TEST_LOGIN = { access: 'test-token', user: { id: 1, name: 'TEST User', email: 'test@example.com', role: 'admin' } }

test.describe('login', () => {
  test('explains when the backend cannot be reached', async ({ page }) => {
    await mockApi(page)
    await page.goto('/login')
    await page.getByLabel('Email / Username').fill('ravi')
    await page.getByLabel('Password', { exact: true }).fill('secret')
    await page.getByRole('button', { name: 'Login' }).click()
    await expect(page.getByRole('alert')).toContainText('Cannot reach the server')
    await expect(page).toHaveURL(/\/login$/)
  })

  test('shows the server message for wrong credentials', async ({ page }) => {
    await mockApi(page, { 'POST /api/auth/login/': { status: 401, body: { detail: 'No active account found with the given credentials' } } })
    await page.goto('/login')
    await page.getByLabel('Email / Username').fill('ravi')
    await page.getByLabel('Password', { exact: true }).fill('wrong')
    await page.getByRole('button', { name: 'Login' }).click()
    await expect(page.getByRole('alert')).toContainText('No active account found')
    await expect(page.getByLabel('Password', { exact: true })).toHaveValue('')
  })

  test('signs in and returns to the page the user was heading to', async ({ page }) => {
    const calls = await mockApi(page, { ...SHELL, 'POST /api/auth/login/': TEST_LOGIN })
    await page.goto('/sales?tab=orders')
    await expect(page).toHaveURL(/\/login$/)
    await page.getByLabel('Email / Username').fill('  ravi  ')
    await page.getByLabel('Password', { exact: true }).fill('secret')
    await page.getByRole('button', { name: 'Login' }).click()
    await expect(page).toHaveURL(/\/sales\?tab=orders$/)
    expect(calls.find((c) => c.key === 'POST /api/auth/login/').body).toEqual({ username: 'ravi', password: 'secret' })
  })

  test('forgot password sends the trimmed email and confirms', async ({ page }) => {
    const calls = await mockApi(page, { 'POST /api/auth/password/forgot/': {} })
    await page.goto('/forgot-password')
    await page.getByLabel('Email').fill('  owner@example.com ')
    await page.getByRole('button', { name: 'Send Reset Link' }).click()
    await expect(page.getByRole('heading', { name: 'Check your email' })).toBeVisible()
    expect(calls.at(-1).body).toEqual({ email: 'owner@example.com' })
  })
})

test.describe('session', () => {
  test('an expired session returns to login with an explanation', async ({ page }) => {
    await signIn(page, 'admin')
    await mockApi(page, { ...SHELL, 'GET /api/dashboard/summary/': { status: 401, body: { detail: 'Token expired' } } })
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByText('Your session has ended. Please log in again to continue.')).toBeVisible()
  })

  test('log out clears the session', async ({ page }) => {
    await signIn(page, 'admin', 'TEST Owner')
    await mockApi(page, { ...SHELL, 'POST /api/auth/logout/': {} })
    await page.goto('/dashboard')
    await page.getByRole('button', { name: 'Account: TEST Owner' }).click()
    await page.getByRole('button', { name: 'Log out' }).click()
    await expect(page).toHaveURL(/\/login$/)
    expect(await page.evaluate(() => sessionStorage.getItem('hipa_token'))).toBeNull()
  })
})
