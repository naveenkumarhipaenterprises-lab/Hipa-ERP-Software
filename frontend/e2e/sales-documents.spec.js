import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

const EMPTY_LIST = { count: 0, next: null, previous: null, results: [] }
const TEST_OPTIONS = {
  customers: [{ id: 11, name: 'TEST Buyer', city: 'TEST City', address: 'TEST billing address', shipping_address: '', phone: '9999999999', email: 'buyer@test.invalid', gstin: '' }],
  products: [{ id: 21, name: 'TEST Chilli', price_per_kg: 300 }, { id: 22, name: 'TEST Turmeric', price_per_kg: 250 }],
  statuses: [], quotation_statuses: [{ value: 'Draft', label: 'Draft' }, { value: 'Sent', label: 'Sent' }, { value: 'Accepted', label: 'Accepted' }],
  invoice_statuses: [], invoice_payment_statuses: [], payment_methods: [{ value: 'UPI', label: 'UPI' }], return_reasons: [], return_statuses: [],
  defaults: { gst_pct: null, quotation_validity_days: 15, quotation_payment_terms: '', quotation_delivery_terms: '', quotation_terms: '',
              invoice_due_days: null, invoice_payment_terms: '', invoice_terms: '' },
}
const QUOTATION = {
  id: 1, quotation_number: 'TEST-QT-1', quotation_date: '2026-10-01', valid_until: '2026-10-16', customer_id: 11, customer_name: 'TEST Buyer',
  company_name: '', billing_address: 'TEST billing address', shipping_address: '', phone: '', email: '', gstin: '', products: 'TEST Chilli',
  subtotal: 3000, discount_amount: 300, taxable_amount: 2700, gst_amount: 135, grand_total: 2835, status: 'Draft', payment_terms: '', delivery_terms: '',
  notes: '', terms_conditions: '', sales_order_id: null, sales_order_number: null, invoice_id: null, invoice_number: null,
  can_edit: true, can_delete: true, can_convert_to_order: true, can_convert_to_invoice: true, next_statuses: ['Sent', 'Accepted', 'Rejected'],
  items: [{ id: 1, product_id: 21, product: 'TEST Chilli', quantity_kg: 10, unit_price: 300, discount_pct: 10, gst_pct: 5, amount: 2835 }],
  status_history: [{ from: null, to: 'Draft', note: 'Created', changed_by: 'TEST User', changed_at: '2026-10-01T10:00:00Z' }],
}

test('build a quotation with several products and live totals', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/sales/options/': TEST_OPTIONS,
    'GET /api/sales/quotations/': EMPTY_LIST,
    'POST /api/sales/quotations/': { status: 201, body: QUOTATION },
    'GET /api/sales/quotations/1/': QUOTATION,
  })
  await page.goto('/sales?tab=quotations')
  await expect(page.getByText('No quotations yet')).toBeVisible()
  await page.getByRole('button', { name: 'New Quotation' }).click()
  const form = page.getByRole('dialog', { name: 'New Quotation' })

  // Nothing is sent until the form is valid
  await form.getByRole('button', { name: 'Save Quotation' }).click()
  await expect(form.getByText('Choose a customer or enter the customer name')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/sales/quotations/')).toBe(false)

  await form.getByLabel('Existing customer').selectOption('11')
  await expect(form.getByLabel('Customer name *')).toHaveValue('TEST Buyer')
  await form.getByLabel('Product, row 1').selectOption('21')
  await form.getByLabel('Quantity, row 1').fill('10')
  await form.getByLabel('Discount percent, row 1').fill('10')
  await form.getByLabel('GST percent, row 1').fill('5')
  await form.getByRole('button', { name: 'Add Product' }).click()
  await form.getByLabel('Product, row 2').selectOption('22')
  await form.getByLabel('Quantity, row 2').fill('4')
  // 3000 − 300 + 135 = 2835 ; + 4 × 250 = 1000 → 3835
  await expect(form.getByText('₹3,835')).toBeVisible()
  await form.getByRole('button', { name: 'Remove row 2' }).click()
  await expect(form.getByText('₹2,835').last()).toBeVisible()

  await form.getByRole('button', { name: 'Save Quotation' }).click()
  await expect(page.getByText('Quotation TEST-QT-1 saved')).toBeVisible()
  const sent = calls.find((c) => c.key === 'POST /api/sales/quotations/').body
  expect(sent).toMatchObject({ customer_id: '11', customer_name: 'TEST Buyer', items: [{ product_id: '21', quantity_kg: 10, discount_pct: 10, gst_pct: 5 }] })
  expect(sent.items[0].unit_price).toBeUndefined() // the product's price is applied by the backend

  // The saved quotation opens with its actions
  const detail = page.getByRole('dialog', { name: 'TEST-QT-1' })
  for (const name of ['Preview', 'Print', 'Download PDF', 'Edit', 'Change Status', 'Convert to Sales Order', 'Convert to Sales Invoice']) {
    await expect(detail.getByRole('button', { name, exact: true })).toBeVisible()
  }
})

test('convert a quotation to an invoice and preview its PDF', async ({ page }) => {
  await signIn(page, 'sales')
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/sales/options/': TEST_OPTIONS,
    'GET /api/sales/quotations/': { count: 1, results: [QUOTATION] },
    'GET /api/sales/quotations/1/': QUOTATION,
    'POST /api/sales/quotations/1/convert-to-invoice/': { status: 201, body: { quotation: { ...QUOTATION, status: 'Converted' }, invoice: { id: 7, invoice_number: 'TEST-INV-7' } } },
  })
  await page.route((url) => url.pathname.endsWith('/sales/quotations/1/pdf/'), (route) =>
    route.fulfill({ status: 200, contentType: 'application/pdf', body: '%PDF-1.4\n%TEST\n' }),
  )
  await page.goto('/sales?tab=quotations')
  await page.getByRole('button', { name: 'Open TEST-QT-1' }).click()
  const detail = page.getByRole('dialog', { name: 'TEST-QT-1' })
  await detail.getByRole('button', { name: 'Preview' }).click()
  await expect(page.getByTitle('Quotation TEST-QT-1')).toBeVisible()
  await page.getByRole('dialog', { name: 'Quotation TEST-QT-1' }).getByRole('button', { name: 'Close' }).click()

  await detail.getByRole('button', { name: 'Convert to Sales Invoice' }).click()
  await page.getByRole('dialog', { name: 'Convert to sales invoice?' }).getByRole('button', { name: 'Create Sales Invoice' }).click()
  await expect(page.getByText('Sales invoice TEST-INV-7 created from TEST-QT-1')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/sales/quotations/1/convert-to-invoice/')).toBe(true)
})

test('sales sub-menu and role rules', async ({ page }) => {
  await signIn(page, 'finance')
  await mockApi(page, { ...SHELL, 'GET /api/sales/options/': TEST_OPTIONS, 'GET /api/sales/invoices/': EMPTY_LIST, 'GET /api/sales/payments/': EMPTY_LIST })
  await page.goto('/sales?tab=invoices')
  const sub = page.getByLabel('Sales sections')
  for (const name of ['Overview', 'Quotations', 'Sales Orders', 'Sales Invoices', 'Payments', 'Returns']) {
    await expect(sub.getByRole('link', { name, exact: true })).toBeVisible()
  }
  await expect(sub.getByRole('link', { name: 'Customers' })).toHaveCount(0) // finance can't open Customers
  await expect(sub.getByRole('link', { name: 'Reports', exact: true })).toHaveCount(0) // nor Reports (managers only)
  await expect(page.getByText('No sales invoices yet')).toBeVisible()
  await expect(page.getByRole('button', { name: 'New Invoice' })).toHaveCount(0) // read-only for finance
  await sub.getByRole('link', { name: 'Payments', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Record Payment' })).toBeVisible() // finance may record receipts
})

test('a payment form sent again (e.g. after an error) carries the same one-time code; a new form gets a new one', async ({ page }) => {
  await signIn(page, 'finance')
  let attempt = 0
  const calls = await mockApi(page, {
    ...SHELL, 'GET /api/sales/options/': TEST_OPTIONS, 'GET /api/sales/payments/': EMPTY_LIST,
    'GET /api/sales/invoices/': { count: 1, results: [{ id: 7, invoice_number: 'TEST-INV-7', customer_name: 'TEST Buyer', balance: 1000 }] },
    'POST /api/sales/payments/': () => {
      attempt += 1
      return attempt === 1 ? { status: 500, body: { detail: 'TEST network hiccup' } }
        : { status: 201, body: { id: 1, receipt_number: 'TEST-RCP-1', invoice_number: 'TEST-INV-7' } }
    },
  })
  await page.goto('/sales?tab=payments')
  await page.getByRole('button', { name: 'Record Payment' }).first().click()
  const form = page.getByRole('dialog', { name: 'Record Payment' })
  await form.getByLabel(/^Amount/).fill('500')
  await form.getByLabel(/Payment method/).selectOption('UPI')
  await form.getByRole('button', { name: 'Save Payment' }).click()
  await expect.poll(() => calls.filter((c) => c.key === 'POST /api/sales/payments/').length).toBe(1)
  await expect(form.getByRole('alert').first()).toBeVisible() // the server error is shown and the form stays open
  await form.getByRole('button', { name: 'Save Payment' }).click()
  await expect(page.getByText('TEST-RCP-1 recorded for TEST-INV-7')).toBeVisible()
  const sent = calls.filter((c) => c.key === 'POST /api/sales/payments/').map((c) => c.body.request_key)
  expect(sent).toHaveLength(2)
  expect(sent[0]).toBeTruthy()
  expect(sent[1]).toBe(sent[0]) // the retry is recognised by the server as the same payment

  await page.getByRole('button', { name: 'Record Payment' }).first().click()
  await page.getByRole('dialog', { name: 'Record Payment' }).getByLabel(/^Amount/).fill('100')
  await page.getByRole('dialog', { name: 'Record Payment' }).getByLabel(/Payment method/).selectOption('UPI')
  await page.getByRole('dialog', { name: 'Record Payment' }).getByRole('button', { name: 'Save Payment' }).click()
  await expect.poll(() => calls.filter((c) => c.key === 'POST /api/sales/payments/').length).toBe(3)
  expect(calls.filter((c) => c.key === 'POST /api/sales/payments/')[2].body.request_key).not.toBe(sent[0]) // a new form: a new code
})
