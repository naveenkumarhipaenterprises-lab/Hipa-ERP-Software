import { api, cleanParams as clean } from './client'

/**
 * Purchase endpoints (Django REST API, /api/v1/purchase/). There are no purchase orders and
 * no purchase invoices: a purchase is recorded once, received with goods receipts (GRN) and
 * paid with supplier payments. Totals, statuses and payment statuses are calculated by the backend.
 *
 * GET /purchase/overview/?range=
 * {
 *   kpis: { total_purchases, purchase_value, pending_purchases, received_purchases, purchase_returns,
 *           supplier_count, outstanding_payments },                       // each { value, change? }
 *   top_materials:        [{ item, quantity, unit, value, purchases }],
 *   supplier_performance: [{ supplier_id, supplier, purchases, purchase_value, on_time_pct, accepted_pct, damaged_pct }],
 *   low_stock:            [{ id, material, current_stock, reorder_level, unit, status, supplier }],
 *   recent_purchases:     [purchase],
 *   insights:             { text?, actions?: string[] },
 * }
 * GET /purchase/trend/?range=&granularity=daily|weekly|monthly   ->  [{ label, value }]
 * GET /purchase/options/  ->  { suppliers, materials, products, purchases, units, categories, *_statuses, return_reasons, payment_methods }
 * GET /purchase/recommendations/?horizon=30|15|7
 * { status: 'ok'|'insufficient_data', message, generated_at, horizon_days,
 *   summary: { items, high, medium, low, estimated_cost },
 *   rows: [{ item_type, item_id, item, unit, current_stock, on_order, avg_daily_demand, demand_basis, lead_time_days,
 *            safety_stock, reorder_point, days_of_cover, recommended_quantity, estimated_cost, priority,
 *            preferred_supplier, last_price, avg_price, price_change_pct, best_supplier, notes: string[] }],
 *   insufficient: [{ item, item_type, reason }] }
 * GET /purchase/recommendations/export/?horizon=   ->  CSV
 *
 * Suppliers      GET/POST /purchase/suppliers/  ?search=&status=&city=&state=&ordering=   · GET/PATCH/DELETE /purchase/suppliers/<id>/
 * Raw materials  GET/POST /purchase/raw-materials/ ?search=&category=&status=&stock_status=  · GET/PATCH/DELETE /purchase/raw-materials/<id>/
 * Usage          GET/POST /purchase/material-movements/  { material_id, type: 'out'|'in', quantity, date?, note?, source? }
 * Purchases      GET/POST /purchase/purchases/ ?search=&status=&payment_status=&supplier=&range=&date_from=&date_to=
 *                GET/PATCH/DELETE /purchase/purchases/<id>/   · POST /purchase/purchases/<id>/cancel/
 *                POST body: { supplier_id, item_type, material_id | product_id, quantity, unit_price?, discount_pct, gst_pct,
 *                             purchase_date, expected_receipt_date?, payment_due_date?, notes? }
 * Goods receipts GET/POST /purchase/goods-receipts/   { purchase_id, received_date, received_quantity, damaged_quantity?,
 *                                                       accepted_quantity?, quality_status?, remarks? }
 * Returns        GET/POST /purchase/returns/  { purchase_id? | supplier_id + item, quantity, return_date, reason, amount?, remarks? }
 *                PATCH /purchase/returns/<id>/ { status: 'completed' | 'cancelled' }
 * Payments       GET/POST /purchase/payments/  { supplier_id | purchase_id, amount, payment_date, payment_method,
 *                                                transaction_reference?, notes?, status: 'paid' | 'pending' }
 *                POST /purchase/payments/<id>/mark-paid/  · DELETE /purchase/payments/<id>/  (scheduled only)
 */
export const purchaseApi = {
  getOverview: ({ range }) => api.get('/purchase/overview/', clean({ range })),
  getTrend: (params) => api.get('/purchase/trend/', clean(params)),
  getOptions: () => api.get('/purchase/options/'),
  getRecommendations: ({ horizon }) => api.get('/purchase/recommendations/', clean({ horizon })),
  exportRecommendations: ({ horizon }) =>
    api.download('/purchase/recommendations/export/', clean({ horizon }), 'hipa-purchase-recommendations.csv'),

  listSuppliers: (params) => api.get('/purchase/suppliers/', clean(params)),
  getSupplier: (id) => api.get(`/purchase/suppliers/${id}/`),
  createSupplier: (body) => api.post('/purchase/suppliers/', body),
  updateSupplier: (id, body) => api.patch(`/purchase/suppliers/${id}/`, body),
  deleteSupplier: (id) => api.delete(`/purchase/suppliers/${id}/`),

  listMaterials: (params) => api.get('/purchase/raw-materials/', clean(params)),
  getMaterial: (id) => api.get(`/purchase/raw-materials/${id}/`),
  createMaterial: (body) => api.post('/purchase/raw-materials/', body),
  updateMaterial: (id, body) => api.patch(`/purchase/raw-materials/${id}/`, body),
  deleteMaterial: (id) => api.delete(`/purchase/raw-materials/${id}/`),
  recordMaterialMovement: (body) => api.post('/purchase/material-movements/', body),

  listPurchases: (params) => api.get('/purchase/purchases/', clean(params)),
  getPurchase: (id) => api.get(`/purchase/purchases/${id}/`),
  createPurchase: (body) => api.post('/purchase/purchases/', body),
  updatePurchase: (id, body) => api.patch(`/purchase/purchases/${id}/`, body),
  cancelPurchase: (id) => api.post(`/purchase/purchases/${id}/cancel/`),
  deletePurchase: (id) => api.delete(`/purchase/purchases/${id}/`),

  listGoodsReceipts: (params) => api.get('/purchase/goods-receipts/', clean(params)),
  createGoodsReceipt: (body) => api.post('/purchase/goods-receipts/', body),

  listReturns: (params) => api.get('/purchase/returns/', clean(params)),
  createReturn: (body) => api.post('/purchase/returns/', body),
  setReturnStatus: (id, status) => api.patch(`/purchase/returns/${id}/`, { status }),

  listPayments: (params) => api.get('/purchase/payments/', clean(params)),
  createPayment: (body) => api.post('/purchase/payments/', body),
  markPaymentPaid: (id, body) => api.post(`/purchase/payments/${id}/mark-paid/`, body),
  deletePayment: (id) => api.delete(`/purchase/payments/${id}/`),
  // A made payment (Paid / Partially Paid): reverses it, so it no longer counts towards the purchase
  cancelPayment: (id) => api.post(`/purchase/payments/${id}/cancel/`),
}
