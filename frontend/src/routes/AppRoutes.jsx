import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Loader from '../components/common/Loader'
import { useAuth } from '../hooks/useAuth'
import AuthLayout from '../layouts/AuthLayout'
import MainLayout from '../layouts/MainLayout'
import { NAV_ITEMS } from '../utils/constants'
import ProtectedRoute from './ProtectedRoute'
import PublicRoute from './PublicRoute'

const Login = lazy(() => import('../pages/Login/Login'))
const ForgotPassword = lazy(() => import('../pages/ForgotPassword/ForgotPassword'))
const ResetPassword = lazy(() => import('../pages/ResetPassword/ResetPassword'))
const Dashboard = lazy(() => import('../pages/Dashboard/Dashboard'))
const NotFound = lazy(() => import('../pages/NotFound/NotFound'))
const SalesPage = lazy(() => import('../modules/sales/SalesPage'))
const InventoryPage = lazy(() => import('../modules/inventory/InventoryPage'))
const CustomersPage = lazy(() => import('../modules/customers/CustomersPage'))
const ProductionPage = lazy(() => import('../modules/production/ProductionPage'))
const MarketingPage = lazy(() => import('../modules/marketing/MarketingPage'))
const SupplyChainPage = lazy(() => import('../modules/supplyChain/SupplyChainPage'))
const QualityPage = lazy(() => import('../modules/quality/QualityPage'))
const FinancePage = lazy(() => import('../modules/finance/FinancePage'))
const ReportsPage = lazy(() => import('../modules/reports/ReportsPage'))
const AIAssistantPage = lazy(() => import('../modules/aiAssistant/AIAssistantPage'))
const SettingsPage = lazy(() => import('../modules/settings/SettingsPage'))

// Page for each module key in NAV_ITEMS (utils/constants.js)
const MODULE_PAGES = {
  dashboard: Dashboard,
  sales: SalesPage,
  inventory: InventoryPage,
  customers: CustomersPage,
  production: ProductionPage,
  marketing: MarketingPage,
  supplyChain: SupplyChainPage,
  quality: QualityPage,
  finance: FinancePage,
  reports: ReportsPage,
  aiAssistant: AIAssistantPage,
  settings: SettingsPage,
}

// Paths and role access come from NAV_ITEMS, so the sidebar and routes can't drift apart
const moduleRoutes = NAV_ITEMS.filter(({ key }) => MODULE_PAGES[key]).map(({ key, path }) => {
  const Page = MODULE_PAGES[key]
  return { key, path: path.slice(1), element: <Page /> }
})

export default function AppRoutes() {
  const { isAuthenticated } = useAuth()

  return (
    <Suspense fallback={<Loader fullScreen />}>
      <Routes>
        <Route element={<PublicRoute />}>
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />
          </Route>
        </Route>

        <Route element={<ProtectedRoute />}>
          <Route element={<MainLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            {moduleRoutes.map((r) => (
              <Route key={r.key} path={r.path} element={<ProtectedRoute module={r.key}>{r.element}</ProtectedRoute>} />
            ))}
          </Route>
        </Route>

        {/* Unknown URLs: inside the app shell when signed in, on the login layout otherwise */}
        <Route element={isAuthenticated ? <MainLayout /> : <AuthLayout />}>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
