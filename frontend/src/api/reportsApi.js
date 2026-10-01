import { api, cleanParams as clean } from './client'

/**
 * Report endpoints (Django REST API).
 *
 * GET /reports/overview/?range=
 * { kpis: { revenue, orders, customers, products_sold_kg } }   // each { value, change? }
 *
 * GET /reports/preview/?type=&range=
 * The server decides what each report shows; the page only draws it.
 * {
 *   title?,
 *   chart:     { title, kind: 'bar' | 'line' | 'area', x_key, format?, series: [{ key, name }], data: [{ ... }] } | null,
 *   breakdown: { title, format?, data: [{ name, value }] } | null,
 *   table:     { columns: [{ key, header, format?, align? }], rows: [{ ... }] },
 * }
 * format is one of: 'inr' | 'number' | 'kg' | 'percent' | 'date' (plain text when omitted)
 *
 * GET  /reports/export/?type=&range=&format=xlsx|csv|pdf   ->  file of the report shown in the preview
 * GET  /reports/?page=&page_size=&type=
 *      { count, results: [{ id, name, type, range_label, format, created_at, created_by, status, download_available }] }
 * POST /reports/                    { type, range, format }   ->  the new report record (may start as "processing")
 * GET  /reports/<id>/download/      ->  the generated file
 */
export const reportsApi = {
  getOverview: ({ range }) => api.get('/reports/overview/', clean({ range })),
  getPreview: ({ type, range }) => api.get('/reports/preview/', clean({ type, range })),
  exportPreview: ({ type, range, format }) =>
    api.download('/reports/export/', clean({ type, range, format }), `hipa-${type}-report.${format === 'xlsx' ? 'xlsx' : format}`),
  list: (params) => api.get('/reports/', clean(params)),
  generate: (report) => api.post('/reports/', report),
  download: (report) => api.download(`/reports/${report.id}/download/`, {}, `hipa-report-${report.id}.${report.format || 'pdf'}`),
}
