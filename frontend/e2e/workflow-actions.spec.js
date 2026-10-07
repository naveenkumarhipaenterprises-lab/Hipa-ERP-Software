import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const sent = (calls, key) => calls.find((c) => c.key === key)?.body

test('a product can be edited (not its stock) and switched off', async ({ page }) => {
  await signIn(page, 'inventory')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/inventory/overview/': {},
    'GET /api/inventory/options/': { items: [], statuses: [] },
    'GET /api/inventory/movements/': { count: 0, results: [] },
    'GET /api/inventory/items/': { count: 1, results: [{ id: 5, product: 'TEST Turmeric', stock_kg: 100, min_stock_kg: 10,
      reorder_level_kg: 30, price_per_kg: 250, stock_value: 25000, status: 'In Stock', is_active: true }] },
    'PATCH /api/inventory/items/5/': { id: 5, product: 'TEST Turmeric', is_active: false },
  })
  await page.goto('/inventory')
  await page.getByRole('button', { name: 'Edit TEST Turmeric' }).click()
  const form = page.getByRole('dialog', { name: 'Edit TEST Turmeric' })
  await expect(form.getByLabel(/Stock \(kg\)/)).toHaveCount(0)
  await form.getByLabel(/Value per kg/).fill('280')
  await form.getByLabel(/Status/).selectOption('false')
  await form.getByRole('button', { name: 'Save Changes' }).click()
  await expect(page.getByText('TEST Turmeric updated')).toBeVisible()
  expect(sent(calls, 'PATCH /api/inventory/items/5/')).toEqual({ product_name: 'TEST Turmeric', price_per_kg: 280, min_stock_kg: 10,
    reorder_level_kg: 30, is_active: false })
})
