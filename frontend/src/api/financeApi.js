import { api, cleanParams as clean } from './client'

/**
 * Finance endpoints (Django REST API). All amounts are in ₹.
 *
 * GET /finance/overview/?range=
 * {
 *   kpis: { revenue, expenses, net_profit, profit_margin_pct },   // each { value, change? }
 *   expense_breakdown:   [{ name, value }],
 *   income_sources:      [{ name, value }],
 *   recent_transactions: [transaction],                         // latest first, up to ~6
 *   budget: { period_label, revenue: { actual, target }, expenses: { actual, target } } | null,
 *   pending_payments:    [{ id, party, kind?: 'supplier' | 'utility' | 'salary' | 'tax' | 'other', due_date, amount, status }],
 *   insights:            { items?: string[], actions?: string[] },   // from the AI engine; empty until it exists
 * }
 *
 * GET /finance/revenue-expenses/?granularity=monthly|quarterly   ->  [{ label, revenue, expenses }]
 * GET /finance/cash-flow/?months=6|3                             ->  [{ label, inflow, outflow }]
 * GET /finance/options/  ->  { income_categories: [{ value, label }], expense_categories: [{ value, label }], statuses: [{ value, label }] }
 *
 * GET  /finance/transactions/?page=&page_size=&search=&type=income|expense&status=
 *      { count, results: [{ id, date, description, type, category, amount, status, reference? }] }
 * POST /finance/transactions/   { type, description, category, amount, date, reference? }
 * PUT  /finance/budget/         { revenue_target, expense_limit }     // current budget period
 */
export const financeApi = {
  getOverview: ({ range }) => api.get('/finance/overview/', clean({ range })),
  getRevenueExpenses: ({ granularity }) => api.get('/finance/revenue-expenses/', clean({ granularity })),
  getCashFlow: ({ months }) => api.get('/finance/cash-flow/', clean({ months })),
  getOptions: () => api.get('/finance/options/'),
  listTransactions: (params) => api.get('/finance/transactions/', clean(params)),
  createTransaction: (tx) => api.post('/finance/transactions/', tx),
  setBudget: (budget) => api.put('/finance/budget/', budget),
}
