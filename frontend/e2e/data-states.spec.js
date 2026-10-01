import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

// The project rule: real data only. With no backend or no records, pages say so — they never invent numbers.
test.describe('no invented data', () => {
  test('backend down: one clear error and no figures', async ({ page }) => {
    await signIn(page, 'admin')
    await mockApi(page, SHELL)
    await page.goto('/dashboard')
    await expect(page.getByRole('alert')).toContainText('Cannot reach the server')
    await expect(page.locator('.stat-card')).toHaveCount(0)
    await expect(page.locator('.app-content')).not.toContainText('₹')
  })

  test('empty data: each section explains itself', async ({ page }) => {
    await signIn(page, 'admin')
    await mockApi(page, { ...SHELL, 'GET /api/dashboard/summary/': {}, 'GET /api/dashboard/sales-trend/': [] })
    await page.goto('/dashboard')
    await expect(page.locator('.stat-card').first()).toContainText('No data available')
    await expect(page.getByText('No sales recorded')).toBeVisible()
    await expect(page.getByText('No recent orders')).toBeVisible()
    await expect(page.getByText('No low stock alerts')).toBeVisible()
  })

  test('real data from the API is shown as sent', async ({ page }) => {
    await signIn(page, 'admin')
    await mockApi(page, {
      ...SHELL,
      'GET /api/dashboard/summary/': { kpis: { total_sales: { value: 1234567, change: 4.2 } }, recent_orders: [{ id: 'TEST-1', customer: 'TEST Buyer', product: 'TEST Chilli', amount: 1500, status: 'Delivered' }] },
      'GET /api/dashboard/sales-trend/': [],
    })
    await page.goto('/dashboard')
    await expect(page.locator('.stat-card').first()).toContainText('₹12,34,567')
    await expect(page.getByRole('row', { name: /TEST-1/ })).toContainText('₹1,500')
  })

  test('AI panels never make up insights', async ({ page }) => {
    await signIn(page, 'admin')
    await mockApi(page, { ...SHELL, 'GET /api/sales/overview/': {}, 'GET /api/sales/trend/': [], 'GET /api/sales/options/': {} })
    await page.goto('/sales')
    await expect(page.getByText(/No insights available yet/)).toBeVisible()
  })
})
