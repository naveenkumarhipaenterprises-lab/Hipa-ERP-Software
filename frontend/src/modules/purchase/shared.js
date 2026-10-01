// Who may change what (mirrors MODULE_WRITE in backend/apps/core/roles.py; the backend enforces it)
export const PURCHASE_MANAGERS = ['admin', 'management', 'purchase']
export const PAYMENT_MANAGERS = ['admin', 'management', 'purchase', 'finance']
export const STOCK_RECORDERS = ['admin', 'management', 'purchase', 'inventory']

export * from '../../utils/display'
