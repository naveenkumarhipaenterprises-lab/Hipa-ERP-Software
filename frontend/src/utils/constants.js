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
const MANAGERS = ['admin', 'management']

/**
 * Sidebar navigation. `roles` controls who sees each module (role-based menus); it mirrors
 * MODULE_READ in backend/apps/core/roles.py. A team role sees only the modules where it does its own work, plus
 * Attendance; Super Admin and Management see everything. `children` are shown as a sub-menu while the module is
 * open: `{ tab }` opens a view of the module (?tab=), `{ to, module }` links to another module the role can open.
 */
export const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: House, roles: MANAGERS },
  {
    key: 'sales',
    label: 'Sales',
    path: '/sales',
    icon: BarChart3,
    roles: ['admin', 'management', 'sales', 'finance'],
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
    roles: ['admin', 'management', 'purchase', 'inventory', 'finance'],
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
  { key: 'inventory', label: 'Inventory', path: '/inventory', icon: Package, roles: ['admin', 'management', 'inventory'] },
  { key: 'customers', label: 'Customers', path: '/customers', icon: Users, roles: ['admin', 'management', 'sales', 'marketing'] },
  { key: 'supplyChain', label: 'Supply Chain', path: '/supply-chain', icon: Truck, roles: ['admin', 'management', 'inventory', 'supply_chain'] },
  { key: 'quality', label: 'Quality', path: '/quality', icon: ShieldCheck, roles: ['admin', 'management', 'quality'] },
  {
    key: 'attendance',
    label: 'Attendance',
    path: '/attendance',
    icon: CalendarCheck,
    roles: ALL, // everyone marks their own attendance; each action needs its own permission (Settings → Users)
    children: [
      // `perms`: the Attendance permissions that open the tab (any one is enough); without them it is hidden
      { tab: 'attendance', label: 'Attendance' },
      { tab: 'employees', label: 'Employees', perms: ['employee_view', 'employee_manage'] },
      { tab: 'leave', label: 'Leave / Permission', perms: ['leave_apply', 'leave_view', 'leave_approve', 'leave_reject'] },
      { tab: 'calendar', label: 'Calendar', perms: ['calendar_view'] },
      { tab: 'reports', label: 'Reports', perms: ['report_view', 'report_export'] },
      { tab: 'settings', label: 'Settings', perms: ['settings_view', 'settings_manage', 'holiday_manage'] },
    ],
  },
  { key: 'reports', label: 'Reports', path: '/reports', icon: FileText, roles: MANAGERS },
  { key: 'marketing', label: 'Marketing', path: '/marketing', icon: Megaphone, roles: ['admin', 'management', 'marketing'] },
  { key: 'aiAssistant', label: 'AI Assistant', path: '/ai-assistant', icon: Bot, roles: MANAGERS },
  { key: 'settings', label: 'Settings', path: '/settings', icon: Settings, roles: MANAGERS },
]

/** Every role the user holds: the main role plus any extra roles (e.g. Purchase + Inventory). */
export const userRoles = (user) =>
  Array.isArray(user?.roles) && user.roles.length ? user.roles : user?.role ? [user.role] : []

/** True when any of the user's roles is in `roles`. The server enforces the same rule. */
export const hasAnyRole = (user, roles) => userRoles(user).some((r) => roles.includes(r))

/** A sub-menu entry with `perms` needs one of those permission codes; `granted` is a list or a { code: bool } map. */
export const hasPerm = (item, granted) => {
  if (!item.perms) return true
  if (Array.isArray(granted)) return item.perms.some((p) => granted.includes(p))
  return item.perms.some((p) => granted?.[p])
}

/** `roles` may be one role or a list of roles. */
export const canAccess = (roles, moduleKey) => {
  const allowed = NAV_ITEMS.find((n) => n.key === moduleKey)?.roles ?? []
  return (Array.isArray(roles) ? roles : [roles]).some((r) => allowed.includes(r))
}

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
