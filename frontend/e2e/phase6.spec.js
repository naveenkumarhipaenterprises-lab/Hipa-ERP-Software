import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

test('dashboard purchase section explains itself when there is no data', async ({ page }) => {
  await signIn(page, 'purchase')
  await mockApi(page, {
    ...SHELL,
    'GET /api/dashboard/summary/': {
      kpis: { active_suppliers: { value: 0 }, purchase_value: { value: 0 }, outstanding_supplier_payments: { value: 0 } },
      purchase_overview: { purchases: 0, pending: 0, received: 0, returns: 0 }, purchase_trend: [], purchase_recommendations: [],
      supplier_performance: [], low_stock_materials: [], upcoming: [],
    },
  })
  await page.goto('/dashboard')
  await expect(page.getByText('No purchases recorded')).toBeVisible()
  await expect(page.getByText('No purchase recommendations')).toBeVisible()
  await expect(page.getByText('No purchase risks')).toBeVisible()
  await expect(page.getByText('Supplier Payments Due')).toBeVisible()
  await expect(page.getByText('Total Sales')).toHaveCount(0) // purchase role has no sales figures
})

test('quality test entry links a test to goods awaiting inspection', async ({ page }) => {
  await signIn(page, 'quality')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': { kpis: {}, product_quality: [], certifications: [], insights: {} },
    'GET /api/quality/trend/': [],
    'GET /api/quality/tests/': { count: 0, results: [] },
    'GET /api/quality/standards/': [],
    'GET /api/quality/options/': {
      pending_receipts: [{ id: 4, grn_number: 'TEST-GRN-4', item: 'TEST Raw Turmeric', item_type: 'material', supplier: 'TEST Farms',
                           received_date: '2026-10-01', quality_status: 'Pending Inspection' }],
      products: [{ id: 21, name: 'TEST Chilli' }], materials: [{ id: 5, name: 'TEST Raw Turmeric' }],
      results: [{ value: 'pass', label: 'Pass' }, { value: 'fail', label: 'Fail' }], audit_types: [],
    },
    'POST /api/quality/tests/': { status: 201, body: { id: 1, product: 'TEST Raw Turmeric', batch_number: 'LOT-1' } },
  })
  await page.goto('/quality')
  await page.getByRole('button', { name: /New Test Entry/ }).first().click()
  const form = page.getByRole('dialog', { name: 'New Test Entry' })
  await expect(form.getByLabel('Product *')).toHaveCount(0) // only the field for the chosen source is shown
  await form.getByLabel('Goods receipt *').selectOption('4')
  await form.getByLabel('Lot / batch number').fill('LOT-1')
  await form.getByLabel('Result *').selectOption('pass')
  await form.getByLabel('Parameters tested *').fill('TEST moisture 8%')
  await form.getByRole('button', { name: 'Save Result' }).click()
  await expect(page.getByText('Result saved for TEST Raw Turmeric lot LOT-1')).toBeVisible()
  const sent = calls.find((c) => c.key === 'POST /api/quality/tests/').body
  expect(sent).toMatchObject({ goods_receipt_id: '4', batch_number: 'LOT-1', result: 'pass' })
  expect(sent.product_id).toBeUndefined()
})

test('tax & billing settings start empty and save', async ({ page }) => {
  await signIn(page, 'admin')
  const blank = {
    default_sales_gst_pct: null, default_purchase_gst_pct: null, quotation_validity_days: null, quotation_payment_terms: '',
    quotation_delivery_terms: '', quotation_terms: '', invoice_due_days: null, invoice_payment_terms: '', invoice_terms: '',
    bank_name: '', bank_account_name: '', bank_account_number: '', bank_ifsc: '', upi_id: '', authorised_signatory: '',
    default_supplier_credit_days: null,
  }
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/settings/options/': { timezones: [], date_formats: [], time_formats: [], currencies: [], languages: [], roles: [], user_statuses: [], backup_retention: [] },
    'GET /api/settings/billing/': blank,
    'PUT /api/settings/billing/': (req) => ({ ...blank, ...req.postDataJSON() }),
  })
  await page.goto('/settings?section=billing')
  const quotations = page.getByRole('region', { name: 'Quotations' }).or(page.locator('section.card', { hasText: 'Defaults for new quotations' }))
  await expect(quotations.getByLabel('Valid for (days)')).toHaveValue('')
  await quotations.getByLabel('Valid for (days)').fill('0')
  await quotations.getByRole('button', { name: 'Save Changes' }).click()
  await expect(quotations.getByText('Enter whole days, 1–365')).toBeVisible()
  await quotations.getByLabel('Valid for (days)').fill('15')
  await quotations.getByRole('button', { name: 'Save Changes' }).click()
  await expect(page.getByText('Quotation settings saved')).toBeVisible()
  expect(calls.find((c) => c.key === 'PUT /api/settings/billing/').body).toMatchObject({ quotation_validity_days: '15' })
})
