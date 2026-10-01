import { api, cleanParams as clean } from './client'

/**
 * Sales endpoints (Django REST API). Flow: Customer → Quotation → (accepted) → Sales Order → Sales Invoice → Payment.
 * Line totals (subtotal − discount + GST), statuses, numbers and PDFs are produced by the backend.
 *
 * GET /sales/overview/?range=&product=
 * {
 *   kpis: { total_sales, total_orders, quantity_sold_kg, new_customers },   // each { value, change? }; sales are net of GST
 *   product_share, customer_types, products, top_customers, insights,
 *   quotations: { count, value, draft, sent, accepted, rejected, expired, converted, converted_value, conversion_rate_pct },
 * }
 * GET /sales/trend/?range=&product=&granularity=daily|weekly   ->  [{ label, sales }]
 * GET /sales/options/
 * { customers: [{ id, name, contact_person, phone, email, city, address, shipping_address, gstin }],
 *   products: [{ id, name, price_per_kg, stock_kg }], statuses, quotation_statuses, invoice_statuses,
 *   invoice_payment_statuses, payment_methods, return_reasons, return_statuses,
 *   defaults: { gst_pct, quotation_validity_days, quotation_payment_terms, quotation_delivery_terms, quotation_terms,
 *               invoice_due_days, invoice_payment_terms, invoice_terms } }   // from Settings → Tax & Billing; empty until set
 *
 * Orders     GET /sales/orders/ · GET /sales/orders/<id>/ · POST /sales/orders/ { customer_id, order_date, notes?, items[] }
 *            POST /sales/orders/<id>/cancel/ · POST /sales/orders/<id>/convert-to-invoice/ { invoice_date?, due_date? }
 * Quotations GET/POST /sales/quotations/ ?search=&status=&customer=&range=&date_from=&date_to=
 *            GET/PATCH/DELETE /sales/quotations/<id>/ · POST /sales/quotations/<id>/status/ { status, note? }
 *            GET /sales/quotations/<id>/pdf/?download=1
 *            POST /sales/quotations/<id>/convert-to-order/ · POST /sales/quotations/<id>/convert-to-invoice/
 *            body: { customer_id?, customer_name, company_name, billing_address, shipping_address, phone, email, gstin,
 *                    quotation_date, valid_until, payment_terms, delivery_terms, notes, terms_conditions, status?,
 *                    items: [{ product_id, quantity_kg, unit_price?, discount_pct?, gst_pct? }] }
 * Invoices   GET/POST /sales/invoices/ ?search=&status=&payment_status=&customer=&range=&date_from=&date_to=
 *            GET/PATCH /sales/invoices/<id>/ · POST /sales/invoices/<id>/cancel/ · GET /sales/invoices/<id>/pdf/?download=1
 * Payments   GET/POST /sales/payments/ { invoice_id, amount, payment_date, payment_method, reference?, notes? }
 *            POST /sales/payments/<id>/cancel/
 * Returns    GET/POST /sales/returns/ { invoice_id, product_id, quantity_kg, return_date, reason, amount?, restock, remarks? }
 *            PATCH /sales/returns/<id>/ { status: 'completed' | 'cancelled' }
 */
export const salesApi = {
  getOverview: ({ range, product }) => api.get('/sales/overview/', clean({ range, product })),
  getTrend: ({ range, product, granularity }) => api.get('/sales/trend/', clean({ range, product, granularity })),
  getOptions: () => api.get('/sales/options/'),

  listOrders: (params) => api.get('/sales/orders/', clean(params)),
  getOrder: (id) => api.get(`/sales/orders/${id}/`),
  createOrder: (order) => api.post('/sales/orders/', order),
  cancelOrder: (id) => api.post(`/sales/orders/${id}/cancel/`),
  orderToInvoice: (id, body = {}) => api.post(`/sales/orders/${id}/convert-to-invoice/`, body),

  listQuotations: (params) => api.get('/sales/quotations/', clean(params)),
  getQuotation: (id) => api.get(`/sales/quotations/${id}/`),
  createQuotation: (body) => api.post('/sales/quotations/', body),
  updateQuotation: (id, body) => api.patch(`/sales/quotations/${id}/`, body),
  deleteQuotation: (id) => api.delete(`/sales/quotations/${id}/`),
  setQuotationStatus: (id, status, note) => api.post(`/sales/quotations/${id}/status/`, clean({ status, note })),
  quotationPdf: (id) => api.blob(`/sales/quotations/${id}/pdf/`),
  downloadQuotationPdf: (id) => api.download(`/sales/quotations/${id}/pdf/`, { download: 1 }, `quotation-${id}.pdf`),
  quotationToOrder: (id, body = {}) => api.post(`/sales/quotations/${id}/convert-to-order/`, body),
  quotationToInvoice: (id, body = {}) => api.post(`/sales/quotations/${id}/convert-to-invoice/`, body),

  listInvoices: (params) => api.get('/sales/invoices/', clean(params)),
  getInvoice: (id) => api.get(`/sales/invoices/${id}/`),
  createInvoice: (body) => api.post('/sales/invoices/', body),
  updateInvoice: (id, body) => api.patch(`/sales/invoices/${id}/`, body),
  cancelInvoice: (id) => api.post(`/sales/invoices/${id}/cancel/`),
  invoicePdf: (id) => api.blob(`/sales/invoices/${id}/pdf/`),
  downloadInvoicePdf: (id) => api.download(`/sales/invoices/${id}/pdf/`, { download: 1 }, `invoice-${id}.pdf`),

  listPayments: (params) => api.get('/sales/payments/', clean(params)),
  createPayment: (body) => api.post('/sales/payments/', body),
  cancelPayment: (id) => api.post(`/sales/payments/${id}/cancel/`),

  listReturns: (params) => api.get('/sales/returns/', clean(params)),
  createReturn: (body) => api.post('/sales/returns/', body),
  setReturnStatus: (id, status) => api.patch(`/sales/returns/${id}/`, { status }),
}
