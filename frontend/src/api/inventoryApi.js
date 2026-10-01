import { api, cleanParams as clean } from './client'

/**
 * Inventory endpoints (Django REST API).
 *
 * GET /inventory/overview/?range=
 * {
 *   kpis: { total_stock_kg, low_stock_items, stock_value, active_products },   // each { value, change? }
 *   stock_levels:  [{ product, stock_kg }],
 *   status_counts: [{ status, count }],                 // e.g. In Stock / Low Stock / Critical
 *   low_stock:     [{ id, product, stock_kg, reorder_level_kg, severity: 'low' | 'critical' }],
 *   movements:     [{ id, type: 'in' | 'out', product, quantity_kg, created_at, note? }],   // most recent first
 *   insights:      { text?, actions?: string[] },       // from the AI engine; empty until it exists
 * }
 *
 * GET /inventory/options/  ->  { items: [{ id, name, stock_kg }], statuses: [{ value, label }] }
 *
 * GET /inventory/items/?page=&page_size=&search=&status=
 * { count, results: [{ id, product, stock_kg, min_stock_kg, reorder_level_kg, price_per_kg, stock_value, status, updated_at }] }
 *
 * GET /inventory/movements/?item=&page_size=   ->  { count, results: [movement] }
 * GET /inventory/items/export/                  ->  CSV file of all items
 *
 * POST /inventory/items/      { product_name, opening_stock_kg, price_per_kg, min_stock_kg, reorder_level_kg }
 * POST /inventory/movements/  { item_id, type: 'in' | 'out', quantity_kg, note? }
 */
export const inventoryApi = {
  getOverview: ({ range }) => api.get('/inventory/overview/', clean({ range })),
  getOptions: () => api.get('/inventory/options/'),
  listItems: (params) => api.get('/inventory/items/', clean(params)),
  listMovements: (params) => api.get('/inventory/movements/', clean(params)),
  createItem: (item) => api.post('/inventory/items/', item),
  recordMovement: (movement) => api.post('/inventory/movements/', movement),
  exportItems: () => api.download('/inventory/items/export/', {}, 'hipa-inventory-report.csv'),
}
