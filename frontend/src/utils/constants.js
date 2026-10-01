import {
  Bot,
  BarChart3,
  Database,
  Factory,
  FileText,
  House,
  Megaphone,
  Package,
  Settings,
  ShieldCheck,
  Truck,
  Users,
} from 'lucide-react'

export const ROLES = {
  ADMIN: 'admin',
  MANAGEMENT: 'management',
  SALES: 'sales',
  INVENTORY: 'inventory',
  PRODUCTION: 'production',
  MARKETING: 'marketing',
  FINANCE: 'finance',
  QUALITY: 'quality',
}

export const ROLE_LABELS = {
  admin: 'Super Admin',
  management: 'Management',
  sales: 'Sales Team',
  inventory: 'Inventory Team',
  production: 'Production Team',
  marketing: 'Marketing Team',
  finance: 'Finance Team',
  quality: 'Quality Team',
}

const ALL = Object.values(ROLES)

/** Sidebar navigation. `roles` controls who sees each module (role-based menus). */
export const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', path: '/dashboard', icon: House, roles: ALL },
  { key: 'sales', label: 'Sales', path: '/sales', icon: BarChart3, roles: ['admin', 'management', 'sales', 'marketing', 'finance'] },
  { key: 'inventory', label: 'Inventory', path: '/inventory', icon: Package, roles: ['admin', 'management', 'inventory', 'production'] },
  { key: 'production', label: 'Production', path: '/production', icon: Factory, roles: ['admin', 'management', 'production', 'inventory', 'quality'] },
  { key: 'marketing', label: 'Marketing', path: '/marketing', icon: Megaphone, roles: ['admin', 'management', 'marketing'] },
  { key: 'customers', label: 'Customers', path: '/customers', icon: Users, roles: ['admin', 'management', 'sales', 'marketing'] },
  { key: 'supplyChain', label: 'Supply Chain', path: '/supply-chain', icon: Truck, roles: ['admin', 'management', 'inventory', 'quality'] },
  { key: 'quality', label: 'Quality', path: '/quality', icon: ShieldCheck, roles: ['admin', 'management', 'quality', 'production'] },
  { key: 'finance', label: 'Finance', path: '/finance', icon: Database, roles: ['admin', 'management', 'finance'] },
  { key: 'aiAssistant', label: 'AI Assistant', path: '/ai-assistant', icon: Bot, roles: ALL },
  { key: 'reports', label: 'Reports', path: '/reports', icon: FileText, roles: ALL },
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
