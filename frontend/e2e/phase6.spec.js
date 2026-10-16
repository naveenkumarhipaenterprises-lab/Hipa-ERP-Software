import { expect, test } from '@playwright/test'
import { mockApi, SHELL, signIn } from './helpers'

test('dashboard purchase section explains itself when there is no data', async ({ page }) => {
  await signIn(page, 'management') // the Dashboard is for Super Admin and Management
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
  await form.getByLabel('Parameter 1', { exact: true }).fill('Moisture')
  await form.getByLabel('Value 1', { exact: true }).fill('8.25')
  await form.getByRole('button', { name: 'Add Parameter' }).click()
  await expect(form.getByLabel('Value 1', { exact: true })).toHaveValue('8.25') // entered values stay
  await form.getByLabel('Parameter 2', { exact: true }).fill('Ash')
  await form.getByLabel('Value 2', { exact: true }).fill('abc')
  await form.getByRole('button', { name: 'Save Result' }).click()
  await expect(form.getByText('Row 2: the value must be a number, e.g. 8.5.')).toBeVisible() // not turned into 0
  await form.getByLabel('Value 2', { exact: true }).fill('3.1')
  await form.getByRole('button', { name: 'Add Parameter' }).click()
  await form.getByRole('button', { name: 'Remove parameter 3' }).click()
  await form.getByRole('button', { name: 'Save Result' }).click()
  await expect(page.getByText('Result saved for TEST Raw Turmeric lot LOT-1')).toBeVisible()
  const sent = calls.find((c) => c.key === 'POST /api/quality/tests/').body
  expect(sent).toMatchObject({ goods_receipt_id: '4', batch_number: 'LOT-1', result: 'pass',
    readings: [{ parameter: 'Moisture', value: '8.25' }, { parameter: 'Ash', value: '3.1' }] })
  expect(sent.product_id).toBeUndefined()
})

test('a GRN recorded as Passed can be tested; its number shows after reloading', async ({ page }) => {
  await signIn(page, 'quality')
  const saved = { id: 9, product: 'TEST Pepper', item_type: 'material', goods_receipt_id: 4, grn_number: 'TEST-GRN-4', batch_number: 'LOT-9',
    test_date: '2026-10-10', parameters: 'Moisture: 11.5', readings: [{ parameter: 'Moisture', value: '11.5' }], result: 'Pass', status: 'Approved' }
  const unlinked = { ...saved, id: 8, goods_receipt_id: null, grn_number: null, batch_number: 'OLD-1' }
  let rows = [unlinked]
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': { kpis: {}, product_quality: [], certifications: [], insights: {} },
    'GET /api/quality/trend/': [],
    'GET /api/quality/tests/': () => ({ count: rows.length, results: rows }),
    'GET /api/quality/standards/': [],
    'GET /api/quality/options/': {
      pending_receipts: [],
      goods_receipts: [{ id: 4, grn_number: 'TEST-GRN-4', item: 'TEST Pepper', item_type: 'material', supplier: 'TEST Farms',
                         received_date: '2026-10-10', quality_status: 'Passed' }],
      products: [], materials: [{ id: 5, name: 'TEST Pepper' }], results: [{ value: 'pass', label: 'Pass' }], audit_types: [],
    },
    'POST /api/quality/tests/': () => {
      rows = [saved, unlinked]
      return { status: 201, body: saved }
    },
  })
  await page.goto('/quality')
  await page.getByRole('button', { name: /New Test Entry/ }).first().click()
  const form = page.getByRole('dialog', { name: 'New Test Entry' })
  await expect(form.getByLabel('Testing *')).toHaveValue('receipt')
  await form.getByLabel('Goods receipt *').selectOption('4')
  await form.getByLabel('Lot / batch number').fill('LOT-9')
  await form.getByLabel('Result *').selectOption('pass')
  await form.getByLabel('Parameter 1', { exact: true }).fill('Moisture')
  await form.getByLabel('Value 1', { exact: true }).fill('11.5')
  await form.getByRole('button', { name: 'Save Result' }).click()
  await expect(page.getByText('Result saved for TEST Pepper lot LOT-9')).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/quality/tests/').body).toMatchObject({ goods_receipt_id: '4' })
  await page.reload()
  const table = page.getByRole('table', { name: 'Quality test results' })
  await expect(table.getByRole('row', { name: /LOT-9/ }).getByRole('cell', { name: 'TEST-GRN-4' })).toBeVisible()
  await expect(table.getByRole('row', { name: /OLD-1/ }).getByRole('cell', { name: '—' }).first()).toBeVisible() // unlinked stays —
})

test('quality certifications: add with a certificate, then edit and delete', async ({ page }) => {
  await signIn(page, 'admin') // deleting is for Super Admins only
  const cert = { id: 3, name: 'TEST FSSAI License', issuing_authority: 'TEST FSSAI', certificate_number: 'TEST-123', category: 'FSSAI License',
    category_value: 'fssai', issue_date: '2026-01-10', valid_until: '2027-01-09', status: 'Active', status_value: 'active', notes: null,
    document: { name: 'TEST-fssai.pdf', type: 'application/pdf', size: 2048 } }
  let certifications = []
  let rejectNext = true
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': () => ({ kpis: {}, product_quality: [], certifications, insights: {} }),
    'GET /api/quality/trend/': [],
    'GET /api/quality/tests/': { count: 0, results: [] },
    'GET /api/quality/audits/': { count: 0, results: [] },
    'GET /api/quality/options/': { pending_receipts: [], products: [], materials: [], results: [], audit_types: [],
      certification_categories: [{ value: 'fssai', label: 'FSSAI License' }, { value: 'iso', label: 'ISO Certification' }],
      certification_statuses: [{ value: 'active', label: 'Active' }, { value: 'pending', label: 'Pending Verification' }] },
    'POST /api/quality/certifications/': () => {
      if (rejectNext) {
        rejectNext = false
        return { status: 400, body: { document: ['This file is not a real PDF file.'] } }
      }
      certifications = [cert]
      return { status: 201, body: cert }
    },
    'PATCH /api/quality/certifications/3/': () => {
      certifications = [{ ...cert, certificate_number: 'TEST-999' }]
      return certifications[0]
    },
    'GET /api/quality/certifications/3/document/': { status: 200, body: 'TEST' },
    'DELETE /api/quality/certifications/3/': () => {
      certifications = []
      return {}
    },
  })
  await page.goto('/quality')
  const card = page.locator('.card').filter({ has: page.getByRole('heading', { name: 'Quality Certifications' }) })
  await expect(card.getByText('No certifications recorded')).toBeVisible()
  await expect(card.getByRole('button', { name: 'Upload Certificate' })).toBeVisible()
  await card.getByRole('button', { name: 'Add Certification' }).first().click()
  const form = page.getByRole('dialog', { name: 'Add Certification' })
  await form.getByLabel(/Certification Name/).fill('TEST FSSAI License')
  await form.getByLabel(/Issue Date/).fill('2026-01-10')
  await form.getByLabel(/Expiry Date/).fill('2025-12-31')
  await form.getByLabel('Certificate Document').setInputFiles({ name: 'TEST.exe', mimeType: 'application/octet-stream', buffer: Buffer.from('MZ') })
  await form.getByRole('button', { name: 'Save Certification' }).click()
  await expect(form.getByText("The expiry date can't be before the issue date")).toBeVisible()
  await expect(form.getByText('Upload a PDF, JPG, JPEG or PNG file.')).toBeVisible()
  expect(calls.some((c) => c.key === 'POST /api/quality/certifications/')).toBe(false) // nothing sent
  await form.getByLabel(/Expiry Date/).fill('2027-01-09')
  await form.getByLabel('Certificate Document').setInputFiles({ name: 'TEST-fssai.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF-1.4 TEST') })
  await form.getByRole('button', { name: 'Save Certification' }).click()
  await expect(form.getByText('This file is not a real PDF file.')).toBeVisible() // the server's refusal, not a false success
  await expect(page.getByText('TEST FSSAI License added')).toHaveCount(0)
  await form.getByRole('button', { name: 'Save Certification' }).click()
  await expect(page.getByText('TEST FSSAI License added')).toBeVisible()
  const sentBody = calls.filter((c) => c.key === 'POST /api/quality/certifications/').at(-1).body
  expect(String(sentBody)).toContain('TEST-fssai.pdf') // the real file is uploaded with the details

  await page.reload()
  await expect(card.getByText('TEST FSSAI License')).toBeVisible()
  await expect(card.getByText('Certificate: TEST-fssai.pdf')).toBeVisible()
  await card.getByRole('button', { name: 'Open certificate of TEST FSSAI License' }).click()
  const preview = page.getByRole('dialog', { name: 'TEST-fssai.pdf' })
  await expect(preview.locator('iframe')).toBeVisible() // fetched with the user's sign-in
  expect(calls.some((c) => c.key === 'GET /api/quality/certifications/3/document/')).toBe(true)
  await preview.getByRole('button', { name: /close/i }).first().click()
  await card.getByRole('button', { name: 'View TEST FSSAI License' }).click()
  await expect(page.getByRole('dialog', { name: 'TEST FSSAI License' }).getByText('09 Jan 2027')).toBeVisible()
  await page.getByRole('dialog', { name: 'TEST FSSAI License' }).getByRole('button', { name: /close/i }).first().click()
  await card.getByRole('button', { name: 'Edit TEST FSSAI License' }).click()
  const edit = page.getByRole('dialog', { name: 'Edit TEST FSSAI License' })
  await expect(edit.getByLabel(/Certificate Number/)).toHaveValue('TEST-123')
  await expect(edit.getByText('TEST-fssai.pdf')).toBeVisible()
  await edit.getByLabel(/Certificate Number/).fill('TEST-999')
  await edit.getByRole('button', { name: 'Save Changes' }).click()
  await expect(page.getByText('TEST FSSAI License updated')).toBeVisible()
  await expect(card.getByText(/No\. TEST-999/)).toBeVisible()

  await card.getByRole('button', { name: 'Delete TEST FSSAI License' }).click()
  await page.getByRole('dialog', { name: 'Delete certification?' }).getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText('TEST FSSAI License deleted')).toBeVisible()
  await expect(card.getByText('No certifications recorded')).toBeVisible()
})

test('quality standards are added on screen', async ({ page }) => {
  await signIn(page, 'quality')
  let standards = []
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': { kpis: {}, product_quality: [], certifications: [], insights: {} },
    'GET /api/quality/trend/': [],
    'GET /api/quality/tests/': { count: 0, results: [] },
    'GET /api/quality/audits/': { count: 0, results: [] },
    'GET /api/quality/options/': { pending_receipts: [], products: [{ id: 21, name: 'TEST Chilli' }], materials: [], results: [], audit_types: [] },
    'GET /api/quality/standards/': () => standards,
    'POST /api/quality/standards/': () => {
      standards = [{ id: 1, parameter: 'Moisture', limit: '≤ 10%', product_id: 21, applies_to: 'TEST Chilli' }]
      return { status: 201, body: standards[0] }
    },
  })
  await page.goto('/quality')
  await page.getByRole('button', { name: 'Quality Standards' }).click()
  const win = page.getByRole('dialog', { name: 'Quality Standards' })
  await expect(win.getByText('No standards defined')).toBeVisible()
  await win.getByRole('button', { name: 'Add Standard' }).click()
  const form = page.getByRole('dialog', { name: 'Add Standard' })
  await form.getByLabel(/^Parameter/).fill('Moisture')
  await form.getByLabel(/^Limit/).fill('≤ 10%')
  await form.getByLabel(/^Applies to/).selectOption('21')
  await form.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByText('Moisture added')).toBeVisible()
  await expect(win.getByRole('cell', { name: 'TEST Chilli' })).toBeVisible()
  expect(calls.find((c) => c.key === 'POST /api/quality/standards/').body).toEqual({ parameter: 'Moisture', limit: '≤ 10%', product_id: '21' })
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

test('saved test parameters load for editing and save again', async ({ page }) => {
  await signIn(page, 'quality')
  const saved = { id: 7, product: 'TEST Chilli', batch_number: 'LOT-7', grn_number: null, test_date: '2026-10-09', result: 'Pass',
    status: 'Approved', notes: null, parameters: 'Moisture: 8.5', readings: [{ parameter: 'Moisture', value: '8.5' }] }
  const calls = await mockApi(page, {
    ...SHELL,
    'GET /api/quality/overview/': { kpis: {}, product_quality: [], certifications: [], insights: {} },
    'GET /api/quality/trend/': [],
    'GET /api/quality/tests/': { count: 1, results: [saved] },
    'GET /api/quality/standards/': [],
    'GET /api/quality/options/': { pending_receipts: [], products: [], materials: [], results: [], audit_types: [] },
    'PATCH /api/quality/tests/7/': { ...saved, parameters: 'Moisture: 9.75; Ash: 3', readings: [{ parameter: 'Moisture', value: '9.75' },
      { parameter: 'Ash', value: '3' }] },
  })
  await page.goto('/quality')
  await page.getByRole('button', { name: 'TEST Chilli' }).click()
  await page.getByRole('button', { name: 'Edit Parameters' }).click()
  const form = page.getByRole('dialog', { name: 'Edit Parameters' })
  await expect(form.getByLabel('Parameter 1', { exact: true })).toHaveValue('Moisture')
  await expect(form.getByLabel('Value 1', { exact: true })).toHaveValue('8.5')
  await form.getByLabel('Value 1', { exact: true }).fill('9.75')
  await form.getByRole('button', { name: 'Add Parameter' }).click()
  await form.getByLabel('Parameter 2', { exact: true }).fill('Ash')
  await form.getByLabel('Value 2', { exact: true }).fill('3')
  await form.getByRole('button', { name: 'Save Parameters' }).click()
  await expect(page.getByText('Parameters saved')).toBeVisible()
  expect(calls.find((c) => c.key === 'PATCH /api/quality/tests/7/').body).toEqual({
    readings: [{ parameter: 'Moisture', value: '9.75' }, { parameter: 'Ash', value: '3' }] })
  await expect(page.getByRole('dialog', { name: 'TEST Chilli' }).getByText('Ash:')).toBeVisible()
})
