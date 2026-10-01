/**
 * Report types offered on the Reports page and the module a role needs to see each one.
 * This is navigation structure only; every figure in a report comes from the API.
 */
export const REPORT_TYPES = [
  { key: 'sales', label: 'Sales Report', module: 'sales' },
  { key: 'inventory', label: 'Inventory Report', module: 'inventory' },
  { key: 'production', label: 'Production Report', module: 'production' },
  { key: 'marketing', label: 'Marketing Report', module: 'marketing' },
  { key: 'customers', label: 'Customer Report', module: 'customers' },
  { key: 'supply_chain', label: 'Supply Chain Report', module: 'supplyChain' },
  { key: 'quality', label: 'Quality Report', module: 'quality' },
  { key: 'finance', label: 'Finance Report', module: 'finance' },
]

export const EXPORT_FORMATS = [
  { value: 'pdf', label: 'PDF' },
  { value: 'xlsx', label: 'Excel' },
  { value: 'csv', label: 'CSV' },
]
