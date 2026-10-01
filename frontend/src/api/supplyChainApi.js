import { api, cleanParams as clean } from './client'

/**
 * Supply chain endpoints (Django REST API).
 *
 * Suppliers, raw materials and purchases are managed in the Purchase module (purchaseApi.js).
 *
 * GET /supply-chain/overview/?range=
 * {
 *   kpis: { total_suppliers, active_shipments, on_time_delivery_pct, procurement_cost, pending_purchases },  // each { value, change? }
 *   flow:             [{ stage, label, count?, detail? }],        // suppliers -> procurement -> warehouse -> distribution -> customers
 *   shipment_summary: { in_transit, delivered, delayed },
 *   raw_materials:    [{ id, material, current_stock, unit, monthly_usage, days_left, status }],
 *   recent_shipments: [{ id, shipment_number, supplier, purchase_number, item, quantity, unit, destination, eta, status }],
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
 */
export const supplyChainApi = {
  getOverview: ({ range }) => api.get('/supply-chain/overview/', clean({ range })),
  getSupplierPerformance: ({ months }) => api.get('/supply-chain/supplier-performance/', clean({ months })),
  getOptions: () => api.get('/supply-chain/options/'),
  listShipments: (params) => api.get('/supply-chain/shipments/', clean(params)),
}
