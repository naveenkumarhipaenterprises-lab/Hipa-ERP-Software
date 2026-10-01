import { api, cleanParams as clean } from './client'

/**
 * Customer endpoints (Django REST API).
 *
 * GET /customers/overview/?range=&type=
 * {
 *   kpis: {
 *     total:   { value, change? },
 *     by_type: [{ type, label, value, change? }],        // one KPI card per customer type
 *   },
 *   type_distribution: [{ name, value }],                // customers per type
 *   locations:         [{ city, customers }],            // most customers first
 *   top_customers:     [{ id, name, amount }],           // ₹ purchases in the range
 *   insights:          string[],                         // from the AI engine; empty until it exists
 * }
 *
 * GET /customers/growth/?period=last_12_months|last_6_months&type=   ->  [{ label, customers }]
 *
 * GET /customers/options/
 * { types: [{ value, label }], statuses: [{ value, label }], offer_channels: [{ value, label }] }
 *
 * GET /customers/?page=&page_size=&search=&type=&status=
 * { count, results: [{ id, name, type, type_label?, city, address?, contact_person, phone, email,
 *                      total_orders, total_purchase, last_order_date, status }] }
 *
 * POST  /customers/          { name, type, contact_person?, phone?, email?, city, address? }
 * PATCH /customers/<id>/     same fields, plus status
 * GET   /customers/export/?search=&type=&status=    ->  CSV file
 * GET   /customers/import/template/                  ->  CSV template
 * POST  /customers/import/   multipart "file"        ->  { created, updated?, skipped?, errors?: [{ row, message }] }
 * POST  /customers/offers/   { segment, channel, message }   ->  { queued }
 */
export const customersApi = {
  getOverview: ({ range, type }) => api.get('/customers/overview/', clean({ range, type })),
  getGrowth: ({ period, type }) => api.get('/customers/growth/', clean({ period, type })),
  getOptions: () => api.get('/customers/options/'),
  list: (params) => api.get('/customers/', clean(params)),
  create: (customer) => api.post('/customers/', customer),
  update: (id, changes) => api.patch(`/customers/${id}/`, changes),
  exportList: (params) => api.download('/customers/export/', clean(params), 'hipa-customers.csv'),
  downloadTemplate: () => api.download('/customers/import/template/', {}, 'hipa-customers-template.csv'),
  importFile: (file) => api.upload('/customers/import/', file),
  sendOffer: (offer) => api.post('/customers/offers/', offer),
}
