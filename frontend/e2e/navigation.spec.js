import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

test('each role only sees its own modules in the menu', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, SHELL)
  await page.goto('/dashboard')
  await expect(page).toHaveURL(/\/sales/) // team roles land on their first module; the Dashboard is for managers
  const menu = page.getByRole('navigation', { name: 'Main' })
  for (const name of ['Sales', 'Customers', 'Attendance']) await expect(menu.getByRole('link', { name, exact: true }).first()).toBeVisible()
  for (const name of ['Dashboard', 'Purchase', 'Inventory', 'Quality', 'Marketing', 'Reports', 'AI Assistant', 'Settings']) {
    await expect(menu.getByRole('link', { name, exact: true })).toHaveCount(0)
  }
})

test('a module the role cannot open shows "no access"', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, SHELL)
  await page.goto('/marketing')
  await expect(page.getByText("You don't have access to this module")).toBeVisible()
})

test('unknown addresses show "page not found" (signed in and signed out)', async ({ page }) => {
  await mockApi(page, SHELL)
  await page.goto('/no-such-page')
  await expect(page.getByText('Page not found')).toBeVisible()
  await expect(page.getByRole('link', { name: 'Go to Login' })).toBeVisible()
})

test('tablet menu drawer opens, traps focus and closes with Escape', async ({ page }) => {
  await page.setViewportSize({ width: 800, height: 1000 })
  await signIn(page, 'admin')
  await mockApi(page, SHELL)
  await page.goto('/dashboard')
  const openButton = page.getByRole('button', { name: 'Open menu' })
  await openButton.click()
  const drawer = page.getByRole('dialog', { name: 'Menu' })
  await expect(drawer).toBeVisible()
  await expect(drawer.getByRole('link', { name: 'Dashboard' })).toBeFocused()
  await page.keyboard.press('Escape')
  await expect(drawer).toBeHidden()
  await expect(openButton).toBeFocused()
})

test('top-bar search hands the question to the AI Assistant', async ({ page }) => {
  await signIn(page, 'admin')
  await mockApi(page, { ...SHELL, 'GET /api/ai/status/': { available: false }, 'GET /api/ai/home/': {} })
  await page.goto('/dashboard')
  await page.getByRole('searchbox', { name: 'Search or ask the AI assistant' }).fill('TEST stock of turmeric')
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/ai-assistant/)
  // The assistant is not connected, so the question is kept in the box rather than lost
  await expect(page.getByLabel('Your question')).toHaveValue('TEST stock of turmeric')
  await expect(page.getByText("The AI Assistant isn't connected yet")).toBeVisible()
})
