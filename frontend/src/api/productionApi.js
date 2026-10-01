import { api, cleanParams as clean } from './client'

/**
 * Production endpoints (Django REST API).
 *
 * The production plan is produced by the backend / AI engine. The frontend never
 * calculates forecasts, required quantities or priorities itself.
 *
 * GET /production/plan/?horizon=30|15|7
 * {
 *   generated_at,                                     // null when no plan exists yet
 *   summary: { total_products, high, medium, low },
 *   rows: [{ product_id, product, stock_kg, forecast_kg, safety_stock_kg,
 *            required_kg, capacity_kg, recommended_kg, priority: 'HIGH' | 'MEDIUM' | 'LOW' }],
 *   insights: { text?, actions?: string[] },
 * }
 * GET /production/plan/export/?horizon=   ->  CSV file
 *
 * GET /production/options/
 * { products: [{ id, name }], lines: [{ id, name }], stages: [{ value, label }] }
 *
 * GET /production/batches/?page=&page_size=&stage=
 * { count, results: [{ id, batch_number, product, quantity_kg, start_date, due_date, line, stage, can_update }] }
 *
 * POST  /production/batches/        { product_id, quantity_kg, start_date, due_date, line_id }
 * PATCH /production/batches/<id>/   { stage }
 */
export const productionApi = {
  getPlan: ({ horizon }) => api.get('/production/plan/', clean({ horizon })),
  exportPlan: ({ horizon }) => api.download('/production/plan/export/', clean({ horizon }), 'hipa-production-plan.csv'),
  getOptions: () => api.get('/production/options/'),
  listBatches: (params) => api.get('/production/batches/', clean(params)),
  scheduleBatch: (batch) => api.post('/production/batches/', batch),
  updateBatch: (id, changes) => api.patch(`/production/batches/${id}/`, changes),
}
