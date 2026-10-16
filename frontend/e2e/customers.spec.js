import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

test('a customer is added with GSTIN and shipping address; a wrong GSTIN is caught first', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/customers/overview/': { kpis: {}, by_type: [], top_customers: [] },
    'GET /api/customers/growth/': [],
    'GET /api/customers/options/': { types: [{ value: 'retailer', label: 'Retailer' }], statuses: [] },
    'GET /api/customers/': { count: 0, results: [] },
    'POST /api/customers/': { status: 201, body: { id: 1, name: 'TEST Traders' } },
  })
  await page.goto('/customers?new=customer')
  const form = page.getByRole('dialog', { name: 'Add Customer' })
  await form.getByLabel(/Customer name/).fill('TEST Traders')
  await form.getByLabel(/Customer type/).selectOption('retailer')
  await form.getByLabel(/^City/).fill('Erode')
  await form.getByLabel(/^Shipping address/).fill('TEST godown, Erode')
  await form.getByLabel(/^GSTIN/).fill('12345')
  await form.getByRole('button', { name: 'Add Customer' }).click()
  await expect(form.getByText('Enter a valid 15-character GSTIN')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/customers/')).toBe(false)
  await form.getByLabel(/^GSTIN/).fill('33ABCDE1234F1Z5')
  await form.getByRole('button', { name: 'Add Customer' }).click()
  await expect(form).toHaveCount(0)
  expect(calls.find((c) => c.key === 'POST /api/customers/').body).toMatchObject({ gstin: '33ABCDE1234F1Z5', shipping_address: 'TEST godown, Erode' })
})
