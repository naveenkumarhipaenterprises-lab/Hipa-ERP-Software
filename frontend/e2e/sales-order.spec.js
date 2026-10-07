import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const TEST_OPTIONS = {
  customers: [{ id: 11, name: 'TEST Buyer' }],
  products: [{ id: 21, name: 'TEST Chilli' }],
  statuses: [{ value: 'pending', label: 'Pending' }],
}

test('create an order end to end, including a server-side rejection', async ({ page }) => {
  await signIn(page, 'sales')
  let attempts = 0
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/sales/overview/': {},
    'GET /api/sales/trend/': [],
    'GET /api/sales/options/': TEST_OPTIONS,
    'GET /api/sales/orders/': { count: 0, results: [] },
    'POST /api/sales/orders/': () =>
      ++attempts === 1
        ? { status: 400, body: { quantity_kg: ['TEST: exceeds available stock'] } }
        : { status: 201, body: { id: 9, order_number: 'TEST-9' } },
  })
  await page.goto('/sales')
  await page.getByRole('button', { name: 'New Order' }).click()
  const form = page.getByRole('dialog', { name: 'New Order' })

  // Nothing is sent until the form is valid
  await form.getByRole('button', { name: 'Create Order' }).click()
  await expect(form.getByText('Customer is required')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/sales/orders/')).toBe(false)

  await form.getByLabel('Customer *').selectOption('11')
  await form.getByLabel('Product *').selectOption('21')
  await form.getByLabel('Quantity (kg) *').fill('12.5')
  await form.getByRole('button', { name: 'Create Order' }).click()
  await expect(form.getByText('TEST: exceeds available stock')).toBeVisible()

  await form.getByLabel('Quantity (kg) *').fill('10')
  await form.getByRole('button', { name: 'Create Order' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByText('Order TEST-9 created')).toBeVisible()
  await expect(page).toHaveURL(/tab=orders/)

  const sent = calls.filter((c) => c.key === 'POST /api/sales/orders/').at(-1).body
  expect(sent).toMatchObject({ customer_id: '11', product_id: '21', quantity_kg: 10 })
})

test('cancelling an order asks first and keeps the dialog open if the server refuses', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, {
    ...SHELL,
    'GET /api/sales/options/': TEST_OPTIONS,
    'GET /api/sales/orders/': { count: 1, results: [{ id: 1, order_number: 'TEST-1', customer: 'TEST Buyer', product: 'TEST Chilli', status: 'Pending', can_cancel: true }] },
    'POST /api/sales/orders/1/cancel/': { status: 409, body: { detail: 'TEST: already dispatched' } },
  })
  await page.goto('/sales?tab=orders')
  await page.getByRole('button', { name: 'Cancel' }).click()
  const dialog = page.getByRole('dialog', { name: 'Cancel this order?' })
  await dialog.getByRole('button', { name: 'Cancel Order' }).click()
  await expect(dialog.getByText('TEST: already dispatched')).toBeVisible()
})

test('an order moves to its next status after confirming', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/sales/options/': TEST_OPTIONS,
    'GET /api/sales/orders/': { count: 1, results: [{ id: 1, order_number: 'TEST-1', customer: 'TEST Buyer', status: 'Processing',
      next_status: { value: 'in_transit', label: 'In Transit' } }] },
    'POST /api/sales/orders/1/status/': { id: 1, order_number: 'TEST-1', status: 'In Transit' },
  })
  await page.goto('/sales?tab=orders')
  await page.getByRole('button', { name: 'Mark TEST-1 In Transit' }).click()
  const dialog = page.getByRole('dialog', { name: 'Mark as In Transit?' })
  await dialog.getByRole('button', { name: 'Mark In Transit' }).click()
  await expect(page.getByText('Order TEST-1 marked In Transit')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/sales/orders/1/status/').body).toEqual({ status: 'in_transit' })
})
