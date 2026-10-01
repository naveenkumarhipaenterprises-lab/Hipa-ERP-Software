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
 * { pending_batches: [{ id, batch_number, product }], results: [{ value, label }], audit_types: [{ value, label }] }
 *
 * GET  /quality/tests/?page=&page_size=&search=&result=
 *      { count, results: [{ id, batch_number, product, test_date, parameters, result, status, notes? }] }
 * POST /quality/tests/      { batch_id, test_date, result, parameters, notes? }
 * GET  /quality/standards/  ->  [{ id, parameter, limit, applies_to? }]
 * POST /quality/audits/     { audit_type, date, auditor? }
 * GET  /quality/report/?range=   ->  CSV file
 */
export const qualityApi = {
  getOverview: ({ range }) => api.get('/quality/overview/', clean({ range })),
  getTrend: ({ range, granularity }) => api.get('/quality/trend/', clean({ range, granularity })),
  getOptions: () => api.get('/quality/options/'),
  listTests: (params) => api.get('/quality/tests/', clean(params)),
  createTest: (test) => api.post('/quality/tests/', test),
  getStandards: () => api.get('/quality/standards/'),
  scheduleAudit: (audit) => api.post('/quality/audits/', audit),
  downloadReport: ({ range }) => api.download('/quality/report/', clean({ range }), 'hipa-quality-report.csv'),
}
