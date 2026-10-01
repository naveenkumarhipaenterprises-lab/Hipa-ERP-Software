import { api, cleanParams as clean } from './client'

/**
 * Sales endpoints (Django REST API).
 *
 * GET /sales/overview/?range=&product=
 * {
 *   kpis: { total_sales, total_orders, quantity_sold_kg, new_customers },   // each { value, change? }
 *   product_share:  [{ name, value }],                  // ₹ sales per product
 *   customer_types: [{ name, value }],                  // orders per customer type
 *   products: [{ id, product, quantity_kg, sales, orders, avg_price, growth?, trend?: number[] }],
 *   top_customers: [{ id, name, type?, amount }],
 *   insights: string[],                                 // from the AI engine; empty until it exists
 * }
 *
 * GET /sales/trend/?range=&product=&granularity=daily|weekly   ->  [{ label, sales }]
 *
 * GET /sales/options/
 * { customers: [{ id, name }], products: [{ id, name }], statuses: [{ value, label }] }
 *
 * GET /sales/orders/?page=&page_size=&search=&status=&range=&product=&customer=
 * { count, results: [{ id, order_number, date, customer, product, quantity_kg, amount, status, can_cancel }] }
 *
 * POST /sales/orders/              { customer_id, product_id, quantity_kg, order_date, notes? }
 * POST /sales/orders/<id>/cancel/
 */
export const salesApi = {
  getOverview: ({ range, product }) => api.get('/sales/overview/', clean({ range, product })),
  getTrend: ({ range, product, granularity }) => api.get('/sales/trend/', clean({ range, product, granularity })),
  getOptions: () => api.get('/sales/options/'),
  listOrders: (params) => api.get('/sales/orders/', clean(params)),
  createOrder: (order) => api.post('/sales/orders/', order),
  cancelOrder: (id) => api.post(`/sales/orders/${id}/cancel/`),
}
