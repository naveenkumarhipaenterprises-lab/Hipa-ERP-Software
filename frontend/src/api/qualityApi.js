import client, { api, cleanParams as clean } from './client'

/** Certification fields + the optional document as multipart/form-data (the file and details are saved together). */
function certificationForm({ document, removeDocument, ...fields }) {
  const form = new FormData()
  for (const [k, v] of Object.entries(fields)) form.append(k, v ?? '')
  if (document) form.append('document', document)
  if (removeDocument) form.append('remove_document', 'true')
  return form
}
const sendForm = async (method, url, form) =>
  (await client.request({ method, url, data: form, headers: { 'Content-Type': 'multipart/form-data' } })).data

/**
 * Quality assurance endpoints (Django REST API).
 *
 * GET /quality/overview/?range=
 * {
 *   kpis: { batches_tested, pass_rate_pct, failed_batches, avg_testing_hours },   // each { value, change? }
 *   product_quality: [{ name, batches, pass_rate_pct }],
 *   certifications:  [certification],
 *   insights:        { items?: string[], actions?: string[] },   // from the AI engine / QA team; empty until available
 * }
 *
 * GET /quality/trend/?range=&granularity=daily|weekly   ->  [{ label, batches, pass_rate_pct }]
 *
 * GET /quality/options/
 * { pending_receipts: [{ id, grn_number, item, item_type, supplier, received_date, quality_status }],   // goods awaiting inspection
 *   goods_receipts: [...same shape],   // every GRN (awaiting inspection first), offered in New Test Entry
 *   products: [{ id, name }], materials: [{ id, name }], results: [{ value, label }], audit_types: [{ value, label }] }
 *
 * GET  /quality/tests/?page=&page_size=&search=&result=
 *      { count, results: [{ id, batch_number, product, item_type, goods_receipt_id, grn_number, test_date, parameters, readings, result,
 *                           status, notes? }] }
 *      readings: [{ parameter, value }] (value = decimal number as text); parameters = the same pairs as one line
 * POST  /quality/tests/      { goods_receipt_id | product_id | material_id, batch_number?, test_date, result, readings, notes? }
 * PATCH /quality/tests/<id>/ { readings }   (changes only the Parameter + Value rows)
 * GET  /quality/standards/  ->  [{ id, parameter, limit, product_id, applies_to }]   POST { parameter, limit, product_id? }
 * PATCH /quality/standards/<id>/   (one limit per parameter + product, or all products; delete: Super Admin)
 * GET  /quality/certifications/   ->  [certification]      POST (multipart) -> certification
 *      certification: { id, name, issuing_authority, certificate_number, category, category_value, issue_date, valid_until,
 *                       status (Active | Expiring Soon | Expired | Pending Verification | Suspended), status_value, notes,
 *                       document: { name, type, size } | null }
 * GET/PATCH (multipart)/DELETE /quality/certifications/<id>/   (PATCH: a new document replaces the old; remove_document=true)
 * GET  /quality/certifications/<id>/document/?download=1   the stored PDF / JPG / PNG (max 4 MB), permission-checked
 * GET  /quality/audits/?page=&page_size=&status=   ->  { count, results: [{ id, audit_type, date, auditor, status, findings, can_update }] }
 * POST /quality/audits/     { audit_type, date, auditor? }
 * POST /quality/audits/<id>/status/   { status: 'completed', findings } | { status: 'cancelled' }   (scheduled audits only)
 * GET  /quality/report/?range=   ->  CSV file
 */
export const qualityApi = {
  getOverview: ({ range }) => api.get('/quality/overview/', clean({ range })),
  getTrend: ({ range, granularity }) => api.get('/quality/trend/', clean({ range, granularity })),
  getOptions: () => api.get('/quality/options/'),
  listTests: (params) => api.get('/quality/tests/', clean(params)),
  createTest: (test) => api.post('/quality/tests/', test),
  updateTestReadings: (id, readings) => api.patch(`/quality/tests/${id}/`, { readings }),
  getStandards: () => api.get('/quality/standards/'),
  createStandard: (body) => api.post('/quality/standards/', body),
  updateStandard: (id, body) => api.patch(`/quality/standards/${id}/`, body),
  listCertifications: () => api.get('/quality/certifications/'),
  createCertification: (values) => sendForm('post', '/quality/certifications/', certificationForm(values)),
  updateCertification: (id, values) => sendForm('patch', `/quality/certifications/${id}/`, certificationForm(values)),
  deleteCertification: (id) => api.delete(`/quality/certifications/${id}/`),
  getCertificationDocument: (id) => api.blob(`/quality/certifications/${id}/document/`),
  downloadCertificationDocument: (id, name) => api.download(`/quality/certifications/${id}/document/`, { download: 1 }, name),
  scheduleAudit: (audit) => api.post('/quality/audits/', audit),
  listAudits: (params) => api.get('/quality/audits/', clean(params)),
  setAuditStatus: (id, body) => api.post(`/quality/audits/${id}/status/`, body),
  downloadReport: ({ range }) => api.download('/quality/report/', clean({ range }), 'hipa-quality-report.csv'),
}
