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
 * { suppliers: [{ id, name }], materials: [{ id, name }], shipment_statuses: [{ value, label }], units: [{ value, label }],
 *   purchases: [{ id, purchase_number, supplier, item, quantity, unit }] }   // open purchases; quantity = still to receive
 *
 * GET  /supply-chain/shipments/?page=&page_size=&search=&status=   ->  { count, results: [shipment] }
 *      shipment: { ..., dispatched_on, delivered_on, quality_passed, can_update, can_link_purchase }
 * POST /supply-chain/shipments/   { purchase_id? | supplier_id + material_id + unit, quantity?, destination, dispatched_on?, eta }
 * PATCH /supply-chain/shipments/<id>/   { quantity?, destination?, dispatched_on?, eta? }   (until delivered)
 * POST /supply-chain/shipments/<id>/status/   { status: 'in_transit' | 'delayed' | 'delivered', delivered_on?, quality_passed? }
 * GET  /supply-chain/shipments/<id>/purchase/   ->  [{ id, purchase_number, supplier, item, quantity, unit, purchase_date }]
 *      open purchases (Pending / Partially Received) from the same supplier for the same item and unit
 * POST /supply-chain/shipments/<id>/purchase/   { purchase_id }   (a shipment saved without a purchase; only the link changes)
 *
 * Customer deliveries (outbound, one per non-cancelled sales order; keyed by the sales order id).
 * Overview adds customer_deliveries: { summary: { total, pending, in_transit, delivered, delayed }, recent: [delivery], can_update }
 *   (null when the role can't see customer deliveries)
 * GET   /supply-chain/customer-deliveries/?page=&page_size=&search=&status=pending|in_transit|delivered|delayed
 *       delivery: { order_id, order_number, customer, order_date, order_status, delivery_status, expected_delivery_date,
 *                   dispatched_on, carrier, tracking_reference, delivered_on, received_by, confirmed_by, confirmed_at, notes,
 *                   can_edit, can_dispatch, can_confirm }
 * GET   /supply-chain/customer-deliveries/<order_id>/   -> delivery + { customer_phone, delivery_address, city, items }
 * PATCH /supply-chain/customer-deliveries/<order_id>/   { expected_delivery_date?, carrier?, tracking_reference?, notes? }
 * POST  /supply-chain/customer-deliveries/<order_id>/dispatch/   { dispatched_on?, carrier?, tracking_reference?, expected_delivery_date? }
 * POST  /supply-chain/customer-deliveries/<order_id>/confirm/    { delivered_on?, received_by?, notes? }
 */
export const supplyChainApi = {
  getOverview: ({ range }) => api.get('/supply-chain/overview/', clean({ range })),
  getSupplierPerformance: ({ months }) => api.get('/supply-chain/supplier-performance/', clean({ months })),
  getOptions: () => api.get('/supply-chain/options/'),
  listShipments: (params) => api.get('/supply-chain/shipments/', clean(params)),
  createShipment: (shipment) => api.post('/supply-chain/shipments/', shipment),
  updateShipment: (id, changes) => api.patch(`/supply-chain/shipments/${id}/`, changes),
  setShipmentStatus: (id, body) => api.post(`/supply-chain/shipments/${id}/status/`, body),
  getLinkablePurchases: (id) => api.get(`/supply-chain/shipments/${id}/purchase/`),
  linkPurchase: (id, purchaseId) => api.post(`/supply-chain/shipments/${id}/purchase/`, { purchase_id: purchaseId }),
  listCustomerDeliveries: (params) => api.get('/supply-chain/customer-deliveries/', clean(params)),
  getCustomerDelivery: (orderId) => api.get(`/supply-chain/customer-deliveries/${orderId}/`),
  updateCustomerDelivery: (orderId, body) => api.patch(`/supply-chain/customer-deliveries/${orderId}/`, body),
  dispatchOrder: (orderId, body) => api.post(`/supply-chain/customer-deliveries/${orderId}/dispatch/`, body),
  confirmDelivery: (orderId, body) => api.post(`/supply-chain/customer-deliveries/${orderId}/confirm/`, body),
}
