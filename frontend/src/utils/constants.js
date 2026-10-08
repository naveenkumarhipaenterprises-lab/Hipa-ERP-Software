import {
  Bot,
  BarChart3,
  CalendarCheck,
  FileText,
  House,
  Megaphone,
  Package,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Truck,
  Users,
} from 'lucide-react'

export const ROLES = {
  ADMIN: 'admin',
  MANAGEMENT: 'management',
  SALES: 'sales',
  PURCHASE: 'purchase',
  INVENTORY: 'inventory',
  MARKETING: 'marketing',
  FINANCE: 'finance',
  QUALITY: 'quality',
  SUPPLY_CHAIN: 'supply_chain',
}

export const ROLE_LABELS = {
  admin: 'Super Admin',
  management: 'Management',
  sales: 'Sales Team',
  purchase: 'Purchase Team',
  inventory: 'Inventory Team',
  marketing: 'Marketing Team',
  finance: 'Accounts Team',
  quality: 'Quality Team',
  supply_chain: 'Supply Chain Team',
}

const ALL = Object.values(ROLES)

/**
 * Sidebar navigation. `roles` controls who sees each module (role-based menus); it mirrors
 * MODULE_READ in backend/apps/core/roles.py. `children` are shown as a sub-menu while the module is
 * open: `{ tab }` opens a view of the module (?tab=), `{ to, module }` links to another module the role can open.
 */
export const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: House, roles: ALL },
  {
    key: 'sales',
    label: 'Sales',
    path: '/sales',
    icon: BarChart3,
    roles: ['admin', 'management', 'sales', 'marketing', 'finance'],
    children: [
      { tab: 'overview', label: 'Overview' },
      { label: 'Customers', to: '/customers', module: 'customers' },
      { tab: 'quotations', label: 'Quotations' },
      { tab: 'orders', label: 'Sales Orders' },
      { tab: 'invoices', label: 'Sales Invoices' },
      { tab: 'payments', label: 'Payments' },
      { tab: 'returns', label: 'Returns' },
      { label: 'Reports', to: '/reports?type=sales', module: 'reports' },
    ],
  },
  {
    key: 'purchase',
    label: 'Purchase',
    path: '/purchase',
    icon: ShoppingCart,
    roles: ['admin', 'management', 'purchase', 'inventory', 'finance', 'supply_chain'],
    children: [
      { tab: 'overview', label: 'Overview' },
      { tab: 'purchases', label: 'Purchases' },
      { tab: 'receipts', label: 'Goods Receipts' },
      { tab: 'returns', label: 'Purchase Returns' },
      { tab: 'payments', label: 'Supplier Payments' },
      { tab: 'suppliers', label: 'Suppliers' },
      { tab: 'materials', label: 'Raw Materials' },
      { tab: 'recommendations', label: 'AI Recommendations' },
    ],
  },
  { key: 'inventory', label: 'Inventory', path: '/inventory', icon: Package, roles: ['admin', 'management', 'inventory', 'purchase', 'supply_chain'] },
  { key: 'customers', label: 'Customers', path: '/customers', icon: Users, roles: ['admin', 'management', 'sales', 'marketing'] },
  { key: 'supplyChain', label: 'Supply Chain', path: '/supply-chain', icon: Truck, roles: ['admin', 'management', 'inventory', 'quality', 'purchase', 'supply_chain'] },
  { key: 'quality', label: 'Quality', path: '/quality', icon: ShieldCheck, roles: ['admin', 'management', 'quality', 'purchase'] },
  {
    key: 'attendance',
    label: 'Attendance',
    path: '/attendance',
    icon: CalendarCheck,
    roles: ALL, // everyone marks their own attendance; each action needs its own permission (Settings → Users)
    children: [
      { tab: 'attendance', label: 'Attendance' },
      { tab: 'employees', label: 'Employees' },
      { tab: 'leave', label: 'Leave / Permission' },
      { tab: 'calendar', label: 'Calendar' },
      { tab: 'reports', label: 'Reports' },
      { tab: 'settings', label: 'Settings' },
    ],
  },
  { key: 'reports', label: 'Reports', path: '/reports', icon: FileText, roles: ALL },
  { key: 'marketing', label: 'Marketing', path: '/marketing', icon: Megaphone, roles: ['admin', 'management', 'marketing'] },
  { key: 'aiAssistant', label: 'AI Assistant', path: '/ai-assistant', icon: Bot, roles: ALL },
  { key: 'settings', label: 'Settings', path: '/settings', icon: Settings, roles: ['admin', 'management'] },
]

export const canAccess = (role, moduleKey) =>
  NAV_ITEMS.find((n) => n.key === moduleKey)?.roles.includes(role) ?? false

/** Chart series colours (styling only; no business meaning). */
export const CHART_COLORS =['#1f7a3d', '#2f6fde', '#f59e0b', '#e5484d', '#8b5cf6', '#0ea5a4', '#a0522d', '#64748b']

/**
 * Date-range filter presets. Only the key is sent to the API; the backend
 * resolves actual dates, so nothing here is tied to a fixed period.
 */
export const DATE_RANGES = [
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'last_3_months', label: 'Last 3 Months' },
  { value: 'this_year', label: 'This Year' },
]

/** Languages offered in the login-page language selector. */
export const LANGUAGES = [{ value: 'en', label: 'English' }]
