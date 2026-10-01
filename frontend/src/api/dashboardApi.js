import { api } from './client'

/**
 * Dashboard endpoints (Django REST API). The backend should only include sections
 * the signed-in user's role may see; the UI also hides cards for modules the role can't open.
 *
 * GET /dashboard/summary/?range=this_month|last_month|last_3_months|this_year
 * {
 *   kpis: {
 *     total_sales:      { value, change? },   // ₹; change = % vs previous period
 *     total_orders:     { value, change? },
 *     total_customers:  { value, change? },
 *     active_suppliers: { value, change? },
 *     net_profit:       { value, change? },   // ₹
 *   },
 *   product_contribution: [{ name, value }],                       // ₹ sales per product
 *   order_status:         [{ status, count }],
 *   recent_orders:        [{ id, customer, product, amount, status }],
 *   low_stock:            [{ id, product, stock_kg, reorder_level_kg, status? }],
 *   top_customers:        [{ id, name, amount }],
 *   upcoming:             [{ id, title, date, category? }],
 * }
 *
 * GET /dashboard/sales-trend/?period=last_12_months|last_6_months
 * [{ label, sales }]   // label e.g. "Jan 2026", sales in ₹
 */
export const dashboardApi = {
  getSummary: (range) => api.get('/dashboard/summary/', { range }),
  getSalesTrend: (period) => api.get('/dashboard/sales-trend/', { period }),
}
