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

const SUPPLY_SHELL = {
  'GET /api/supply-chain/overview/': {},
  'GET /api/supply-chain/supplier-performance/': [],
  'GET /api/supply-chain/options/': {
    suppliers: [{ id: 3, name: 'TEST Farms' }], materials: [{ id: 4, name: 'TEST Raw Chilli' }], units: [{ value: 'kg', label: 'Kilogram (kg)' }],
    shipment_statuses: [{ value: 'in_transit', label: 'In Transit' }],
    purchases: [{ id: 9, purchase_number: 'TEST-PUR-1', supplier: 'TEST Farms', item: 'TEST Raw Chilli', quantity: 80, unit: 'kg' }],
  },
}

test('a shipment is created from a purchase', async ({ page }) => {
  await signIn(page, 'supply_chain')
  const calls = await mockApi(page, { ...SHELL, ...SUPPLY_SHELL, 'POST /api/supply-chain/shipments/': { id: 1, shipment_number: 'TEST-SH-1' } })
  await page.goto('/supply-chain')
  await page.getByRole('button', { name: 'New Shipment' }).first().click()
  const form = page.getByRole('dialog', { name: 'New Shipment' })
  await form.getByLabel('Purchase').selectOption('9')
  await expect(form.getByLabel(/Supplier/)).toHaveCount(0) // comes from the purchase
  await form.getByLabel(/Destination/).fill('TEST Warehouse')
  await form.getByLabel(/Expected arrival/).fill('2099-01-05')
  await form.getByRole('button', { name: 'Create Shipment' }).click()
  await expect(page.getByText('Shipment TEST-SH-1 created')).toBeVisible()
  const body = sent(calls, 'POST /api/supply-chain/shipments/')
  expect(body).toMatchObject({ purchase_id: '9', quantity: '', destination: 'TEST Warehouse', eta: '2099-01-05' })
})

test('a shipment is marked delivered with its quality result', async ({ page }) => {
  await signIn(page, 'supply_chain')
  const calls = await mockApi(page, {
    ...SHELL,
    ...SUPPLY_SHELL,
    'GET /api/supply-chain/shipments/': { count: 1, results: [{ id: 1, shipment_number: 'TEST-SH-1', supplier: 'TEST Farms', item: 'TEST Raw Chilli',
      status: 'In Transit', can_update: true }] },
    'POST /api/supply-chain/shipments/1/status/': { id: 1, shipment_number: 'TEST-SH-1', status: 'Delivered' },
  })
  await page.goto('/supply-chain')
  await page.getByRole('button', { name: 'Track Shipments' }).click()
  await page.getByRole('button', { name: 'Mark TEST-SH-1 delivered' }).click()
  const form = page.getByRole('dialog', { name: 'Mark TEST-SH-1 delivered' })
  await form.getByLabel('Inward quality check').selectOption('true')
  await form.getByRole('button', { name: 'Mark Delivered' }).click()
  await expect(page.getByText('TEST-SH-1 marked Delivered')).toBeVisible()
  expect(sent(calls, 'POST /api/supply-chain/shipments/1/status/')).toMatchObject({ status: 'delivered', quality_passed: 'true' })
})

test('a scheduled audit is completed with its findings', async ({ page }) => {
  await signIn(page, 'quality')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': {},
    'GET /api/quality/trend/': [],
    'GET /api/quality/options/': { audit_statuses: [{ value: 'scheduled', label: 'Scheduled' }], results: [], audit_types: [] },
    'GET /api/quality/tests/': { count: 0, results: [] },
    'GET /api/quality/audits/': { count: 1, results: [{ id: 2, audit_type: 'TEST FSSAI Inspection', date: '2026-10-07', auditor: 'TEST Inspector',
      status: 'Scheduled', findings: null, can_update: true }] },
    'POST /api/quality/audits/2/status/': { id: 2, status: 'Completed' },
  })
  await page.goto('/quality')
  await page.getByRole('button', { name: /^Complete TEST FSSAI Inspection/ }).click()
  const form = page.getByRole('dialog', { name: 'Complete TEST FSSAI Inspection' })
  await form.getByRole('button', { name: 'Mark Completed' }).click()
  await expect(form.getByText(/required/i)).toBeVisible() // findings are required
  await form.getByLabel(/Findings/).fill('TEST: all labels compliant')
  await form.getByRole('button', { name: 'Mark Completed' }).click()
  await expect(page.getByText(/TEST FSSAI Inspection on .* completed/)).toBeVisible()
  expect(sent(calls, 'POST /api/quality/audits/2/status/')).toEqual({ status: 'completed', findings: 'TEST: all labels compliant' })
})

const FINANCE_SHELL = {
  'GET /api/finance/revenue-expenses/': [],
  'GET /api/finance/cash-flow/': [],
  'GET /api/finance/options/': { income_categories: [{ value: 'product_sales', label: 'Product Sales' }],
    expense_categories: [{ value: 'utilities', label: 'Utilities' }], statuses: [] },
}

test('an expense can be recorded as a pending payment', async ({ page }) => {
  await signIn(page, 'finance')
  const calls = await mockApi(page, { ...SHELL, ...FINANCE_SHELL, 'GET /api/finance/overview/': {}, 'POST /api/finance/transactions/': { id: 1 } })
  await page.goto('/finance')
  await page.getByRole('button', { name: 'Record Expense' }).first().click()
  const form = page.getByRole('dialog', { name: 'Record Expense' })
  await form.getByLabel(/Description/).fill('TEST power bill')
  await form.getByLabel(/Category/).selectOption('utilities')
  await form.getByLabel(/Amount/).fill('400')
  await expect(form.getByLabel('Pay to')).toHaveCount(0)
  await form.getByLabel(/Payment/).selectOption('pending')
  await form.getByLabel('Pay to').fill('TEST Electricity Board')
  await form.getByLabel('Due date').fill('2099-01-10')
  await form.getByRole('button', { name: 'Save Expense' }).click()
  await expect(page.getByText(/Expense of .*400.* recorded/)).toBeVisible()
  expect(sent(calls, 'POST /api/finance/transactions/')).toMatchObject({ type: 'expense', status: 'pending', party: 'TEST Electricity Board',
    due_date: '2099-01-10', amount: 400 })
})

test('a pending payment is marked paid with its reference', async ({ page }) => {
  await signIn(page, 'finance')
  const calls = await mockApi(page, {
    ...SHELL,
    ...FINANCE_SHELL,
    'GET /api/finance/overview/': { pending_payments: [{ id: 7, party: 'TEST Electricity Board', kind: 'utility', due_date: '2099-01-10',
      amount: 400, status: 'Pending' }] },
    'POST /api/finance/transactions/7/mark-paid/': { id: 7, status: 'Completed' },
  })
  await page.goto('/finance')
  await page.getByRole('button', { name: 'Mark TEST Electricity Board paid' }).click()
  const form = page.getByRole('dialog', { name: 'Mark TEST Electricity Board paid' })
  await form.getByLabel('Payment reference').fill('TEST-UTR-9')
  await form.getByRole('button', { name: 'Confirm' }).click()
  await expect(page.getByText('TEST Electricity Board marked paid')).toBeVisible()
  expect(sent(calls, 'POST /api/finance/transactions/7/mark-paid/')).toEqual({ reference: 'TEST-UTR-9' })
})

test('a due post is marked published after posting it by hand', async ({ page }) => {
  await signIn(page, 'marketing')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/marketing/overview/': {},
    'GET /api/marketing/performance/': [],
    'GET /api/marketing/audience/': [],
    'GET /api/marketing/options/': { platforms: [], objectives: [], statuses: [] },
    'GET /api/marketing/campaigns/': { count: 0, results: [] },
    'GET /api/marketing/posts/': { count: 1, results: [{ id: 4, platform: 'Instagram', scheduled_for: '2026-10-07T10:00:00+05:30',
      caption: 'TEST Diwali offer', status: 'Scheduled', is_due: true, can_update: true }] },
    'POST /api/marketing/posts/4/status/': { id: 4, status: 'Published' },
  })
  await page.goto('/marketing')
  await page.getByRole('button', { name: 'Content Calendar' }).first().click()
  const calendar = page.getByRole('dialog', { name: 'Content Calendar' })
  await expect(calendar.getByText('Due')).toBeVisible()
  await calendar.getByRole('button', { name: 'Mark the Instagram post published' }).click()
  await page.getByRole('dialog', { name: 'Mark this post published?' }).getByRole('button', { name: 'Mark Published' }).click()
  await expect(page.getByText('Post marked published')).toBeVisible()
  expect(sent(calls, 'POST /api/marketing/posts/4/status/')).toEqual({ status: 'published' })
})
