import { api, cleanParams as clean } from './client'

/**
 * Quality assurance endpoints (Django REST API).
 *
 * GET /quality/overview/?range=
 * {
 *   kpis: { batches_tested, pass_rate_pct, failed_batches, avg_testing_hours },   // each { value, change? }
 *   product_quality: [{ name, batches, pass_rate_pct }],
 *   certifications:  [{ id, name, detail?, valid_until?, status? }],
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
 * GET  /quality/standards/  ->  [{ id, parameter, limit, applies_to? }]
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
  scheduleAudit: (audit) => api.post('/quality/audits/', audit),
  listAudits: (params) => api.get('/quality/audits/', clean(params)),
  setAuditStatus: (id, body) => api.post(`/quality/audits/${id}/status/`, body),
  downloadReport: ({ range }) => api.download('/quality/report/', clean({ range }), 'hipa-quality-report.csv'),
}
