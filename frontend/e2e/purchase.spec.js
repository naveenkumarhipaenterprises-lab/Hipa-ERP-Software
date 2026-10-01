import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const EMPTY_LIST = { count: 0, next: null, previous: null, results: [] }
const TEST_OPTIONS = {
  suppliers: [{ id: 3, name: 'TEST Farms', credit_days: 30 }],
  materials: [{ id: 5, name: 'TEST Raw Turmeric', unit: 'kg', purchase_price: 120, supplier_id: 3 }],
  products: [],
  purchases: [],
  units: [{ value: 'kg', label: 'Kilogram (kg)' }],
  categories: [{ value: 'whole_spice', label: 'Whole Spices' }],
  purchase_statuses: [{ value: 'Pending', label: 'Pending' }],
  payment_statuses: [{ value: 'Pending', label: 'Pending' }],
  quality_statuses: [{ value: 'Pending Inspection', label: 'Pending Inspection' }],
  return_reasons: [{ value: 'Damaged', label: 'Damaged' }],
  return_statuses: [{ value: 'Pending', label: 'Pending' }],
  payment_methods: [{ value: 'UPI', label: 'UPI' }],
  supplier_statuses: [{ value: 'Active', label: 'Active' }],
  material_statuses: [{ value: 'Active', label: 'Active' }],
  supplier_payment_statuses: [{ value: 'Pending', label: 'Pending' }],
}

test('overview shows empty states, never invented numbers, and the sidebar sub-menu', async ({ page }) => {
  await signIn(page, 'purchase')
  await mockApi(page, {
    ...SHELL,
    'GET /api/purchase/options/': TEST_OPTIONS,
    'GET /api/purchase/overview/': { kpis: {}, top_materials: [], supplier_performance: [], low_stock: [], recent_purchases: [], insights: {} },
    'GET /api/purchase/trend/': [],
  })
  await page.goto('/purchase')
  await expect(page.getByRole('heading', { name: 'Purchase', exact: true })).toBeVisible()
  await expect(page.getByText('No purchases in this period')).toBeVisible()
  await expect(page.getByText('No low-stock materials')).toBeVisible()
  await expect(page.getByText('No data available').first()).toBeVisible()
  // No Production module anywhere in the menu
  await expect(page.getByRole('link', { name: 'Production' })).toHaveCount(0)
  await page.getByRole('link', { name: 'Suppliers' }).click()
  await expect(page).toHaveURL(/tab=suppliers/)
})

test('record a purchase with live totals and a server-side rejection', async ({ page }) => {
  await signIn(page, 'purchase')
  let attempts = 0
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/purchase/options/': TEST_OPTIONS,
    'GET /api/purchase/purchases/': EMPTY_LIST,
    'POST /api/purchase/purchases/': () =>
      ++attempts === 1
        ? { status: 400, body: { supplier_id: ['TEST: supplier is inactive'] } }
        : { status: 201, body: { id: 1, purchase_number: 'TEST-PUR-1', item: 'TEST Raw Turmeric' } },
  })
  await page.goto('/purchase?tab=purchases')
  await expect(page.getByText('No purchases recorded yet')).toBeVisible()
  await page.getByRole('button', { name: 'Record Purchase' }).click()
  const form = page.getByRole('dialog', { name: 'Record Purchase' })

  await form.getByLabel('Supplier *').selectOption('3')
  await form.getByLabel('Raw material *').selectOption('5')
  await form.getByLabel('Quantity *').fill('100')
  await form.getByLabel('Discount %').fill('5')
  await form.getByLabel('GST / Tax %').fill('5')
  // Unit price left blank: the material's standard price (₹120) is used. 12,000 − 600 + 570 = 11,970
  const totals = form.getByRole('definition').last()
  await expect(totals).toHaveText('₹11,970')

  await form.getByRole('button', { name: 'Save Purchase' }).click()
  await expect(form.getByText('TEST: supplier is inactive')).toBeVisible()
  await form.getByRole('button', { name: 'Save Purchase' }).click()
  await expect(form).toBeHidden()
  await expect(page.getByText('Purchase TEST-PUR-1 recorded: TEST Raw Turmeric')).toBeVisible()

  const sent = calls.filter((c) => c.key === 'POST /api/purchase/purchases/').at(-1).body
  expect(sent).toMatchObject({ supplier_id: '3', item_type: 'material', material_id: '5', quantity: 100, discount_pct: 5, gst_pct: 5 })
  expect(sent.unit_price).toBeUndefined()
})

test('recommendations say so when there is not enough data', async ({ page }) => {
  await signIn(page, 'purchase')
  await mockApi(page, {
    ...SHELL,
    'GET /api/purchase/options/': TEST_OPTIONS,
    'GET /api/purchase/recommendations/': {
      status: 'insufficient_data', message: 'Insufficient data for AI recommendation.', generated_at: null,
      summary: { items: 0, high: 0, medium: 0, low: 0, estimated_cost: null }, rows: [],
      insufficient: [{ item: 'TEST Raw Turmeric', item_type: 'material', reason: 'TEST: needs 14+ days of usage' }],
    },
  })
  await page.goto('/purchase?tab=recommendations')
  await expect(page.getByText('Insufficient data for AI recommendation.').first()).toBeVisible()
  await expect(page.getByText('TEST: needs 14+ days of usage')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
})

test('roles: finance can open Purchase but not record purchases; sales cannot open it', async ({ page }) => {
  await signIn(page, 'finance')
  await mockApi(page, { ...SHELL, 'GET /api/purchase/options/': TEST_OPTIONS, 'GET /api/purchase/purchases/': EMPTY_LIST, 'GET /api/purchase/payments/': EMPTY_LIST })
  await page.goto('/purchase?tab=purchases')
  await expect(page.getByText('No purchases recorded yet')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Record Purchase' })).toHaveCount(0)
  await page.goto('/purchase?tab=payments')
  await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible()
})

test('sales role has no Purchase menu and gets the no-access page', async ({ page }) => {
  await signIn(page, 'sales')
  await mockApi(page, { ...SHELL })
  await page.goto('/purchase')
  await expect(page.getByText("You don't have access to this module")).toBeVisible()
  await expect(page.getByRole('link', { name: 'Purchase' })).toHaveCount(0)
})
