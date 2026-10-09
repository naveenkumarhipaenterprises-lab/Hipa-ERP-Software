import { api, cleanParams as clean, tokenStorage } from './client'

/**
 * Settings endpoints (Django REST API). Admin / management only; the backend enforces this.
 *
 * GET /settings/options/
 * { timezones, date_formats, time_formats, currencies, languages, roles, user_statuses, backup_retention,
 *   attendance_permissions }   // each [{ value, label }]
 *
 * GET/PUT  /settings/general/    { company_name, tagline?, timezone, date_format, time_format, currency, language }
 * GET/PUT  /settings/company/    { legal_name, address, email, phone, website?, gstin? }
 * GET/PUT  /settings/billing/    { default_sales_gst_pct, default_purchase_gst_pct, quotation_validity_days, quotation_payment_terms,
 *                                  quotation_delivery_terms, quotation_terms, invoice_due_days, invoice_payment_terms, invoice_terms,
 *                                  bank_name, bank_account_name, bank_account_number, bank_ifsc, upi_id, authorised_signatory,
 *                                  default_supplier_credit_days }   // all optional; blank numbers = not set
 *
 * GET   /settings/users/?page=&page_size=&search=   ->  { count, results: [{ id, name, email, role, status, last_login?, attendance_permissions }] }
 * POST  /settings/users/            { name, email, role }        // sends an invitation email
 * PATCH /settings/users/<id>/       { name?, role?, status?, attendance_permissions?: [code] }   // a Super Admin always has all
 *
 * GET   /settings/notifications/    ->  [{ key, title, description?, enabled }]
 * PATCH /settings/notifications/    { key, enabled }
 *
 * GET   /settings/backup/           ->  { automatic, retention_months, last_backup_at?, last_backup_status? }
 * PATCH /settings/backup/           { automatic?, retention_months? }
 * POST  /settings/backup/run/       ->  { status }
 *
 * GET  /settings/integrations/                  ->  [{ key, name, description?, connected, connected_at? }]
 * POST /settings/integrations/<key>/connect/    ->  { connected, redirect_url? }   // redirect_url for OAuth-style set-up
 * POST /settings/integrations/<key>/disconnect/
 *
 * GET   /settings/security/                       ->  { two_factor_enabled }
 * PATCH /settings/security/                       { two_factor_enabled }
 * GET   /settings/security/login-activity/?page=  ->  { count, results: [{ id, user, device?, ip?, location?, time, success }] }
 * POST  /settings/users/<id>/password/           { password }  (Super Admin only)
 * POST  /auth/password/change/                    { current_password, new_password }  ->  { detail, access, refresh }
 *
 * GET /settings/audit-logs/?page=&page_size=&search=   ->  { count, results: [{ id, time, user, action, target? }] }
 */
export const settingsApi = {
  getOptions: () => api.get('/settings/options/'),
  getGeneral: () => api.get('/settings/general/'),
  saveGeneral: (values) => api.put('/settings/general/', values),
  getCompany: () => api.get('/settings/company/'),
  saveCompany: (values) => api.put('/settings/company/', values),
  getBilling: () => api.get('/settings/billing/'),
  saveBilling: (values) => api.put('/settings/billing/', values),

  listUsers: (params) => api.get('/settings/users/', clean(params)),
  inviteUser: (user) => api.post('/settings/users/', user),
  updateUser: (id, changes) => api.patch(`/settings/users/${id}/`, changes),
  // Super Admin only: sets another person's password and signs them out everywhere
  setUserPassword: (id, password) => api.post(`/settings/users/${id}/password/`, { password }),

  getNotifications: () => api.get('/settings/notifications/'),
  setNotification: (key, enabled) => api.patch('/settings/notifications/', { key, enabled }),

  getBackup: () => api.get('/settings/backup/'),
  updateBackup: (changes) => api.patch('/settings/backup/', changes),
  runBackup: () => api.post('/settings/backup/run/'),

  getIntegrations: () => api.get('/settings/integrations/'),
  connectIntegration: (key) => api.post(`/settings/integrations/${key}/connect/`),
  disconnectIntegration: (key) => api.post(`/settings/integrations/${key}/disconnect/`),

  getSecurity: () => api.get('/settings/security/'),
  updateSecurity: (changes) => api.patch('/settings/security/', changes),
  listLoginActivity: (params) => api.get('/settings/security/login-activity/', clean(params)),
  // The server signs out every other session and returns new tokens for this one
  changePassword: async (body) => {
    const res = await api.post('/auth/password/change/', body)
    if (res?.access) tokenStorage.replace(res.access)
    return res
  },

  listAuditLogs: (params) => api.get('/settings/audit-logs/', clean(params)),
}
