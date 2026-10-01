import { api, cleanParams as clean } from './client'

/**
 * Supply chain endpoints (Django REST API).
 *
 * GET /supply-chain/overview/?range=
 * {
 *   kpis: { total_suppliers, active_shipments, on_time_delivery_pct, procurement_cost, pending_orders },  // each { value, change? }
 *   flow:             [{ stage, label, count?, detail? }],        // e.g. farmers -> processing -> warehouse -> distribution -> customers
 *   shipment_summary: { in_transit, delivered, delayed },
 *   raw_materials:    [{ id, material, stock_kg, monthly_usage_kg, days_left, status }],
 *   recent_shipments: [{ id, shipment_number, supplier, destination, eta, status }],
 *   alerts:           [{ id, type: 'error' | 'warning' | 'info' | 'success', title, detail? }],
 *   insights:         { text?, actions?: string[] },              // from the AI engine; empty until it exists
 * }
 *
 * GET /supply-chain/supplier-performance/?months=6|3
 * [{ supplier, quality_pct, on_time_pct, cost_efficiency_pct }]
 *
 * GET /supply-chain/options/
 * { suppliers: [{ id, name }], materials: [{ id, name }], shipment_statuses: [{ value, label }] }
 *
 * GET  /supply-chain/shipments/?page=&page_size=&search=&status=   ->  { count, results: [shipment] }
 * GET  /supply-chain/suppliers/?page=&page_size=&search=
 *      { count, results: [{ id, name, city, contact_person, phone, email, quality_pct, on_time_pct, status }] }
 * POST /supply-chain/suppliers/         { name, city, contact_person?, phone?, email? }
 * POST /supply-chain/purchase-orders/   { supplier_id, material_id, quantity_kg, rate_per_kg?, expected_delivery, notes? }
 */
export const supplyChainApi = {
  getOverview: ({ range }) => api.get('/supply-chain/overview/', clean({ range })),
  getSupplierPerformance: ({ months }) => api.get('/supply-chain/supplier-performance/', clean({ months })),
  getOptions: () => api.get('/supply-chain/options/'),
  listShipments: (params) => api.get('/supply-chain/shipments/', clean(params)),
  listSuppliers: (params) => api.get('/supply-chain/suppliers/', clean(params)),
  createSupplier: (supplier) => api.post('/supply-chain/suppliers/', supplier),
  createPurchaseOrder: (po) => api.post('/supply-chain/purchase-orders/', po),
}
