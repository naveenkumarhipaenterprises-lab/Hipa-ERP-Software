import { Leaf } from 'lucide-react'
import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Loader from '../components/common/Loader'
import RouteErrorBoundary from '../components/common/RouteErrorBoundary'
import Sidebar from '../components/navigation/Sidebar'
import Topbar from '../components/navigation/Topbar'
import { useMediaQuery } from '../hooks/useMediaQuery'

const FOOTER_SLOGANS = {
  '/dashboard': 'Good Food. Good Health. A Better Tomorrow.',
  '/customers': '“Together with our customers, we bring the authentic taste of India to every home.”',
  '/ai-assistant': 'Good Data. Good Decisions. A Spicier Tomorrow.',
  '/quality': 'Quality in Every Step • From Nature to Your Kitchen',
  '/reports': 'Good Marketing. Greater Reach. A Better Tomorrow.',
  '/settings': 'Good Settings. Greater Growth.',
  '/supply-chain': 'Sustainable Sourcing • Reliable Supply • Stronger Communities',
}

const SIDEBAR_ID = 'app-sidebar'

export default function MainLayout() {
  const { pathname } = useLocation()
  const drawer = useMediaQuery('(max-width: 1024px)')
  // The drawer belongs to the page it was opened on, so any navigation closes it
  const [openOn, setOpenOn] = useState(null)
  // Switching between drawer and desktop layouts forgets an open drawer
  const [wasDrawer, setWasDrawer] = useState(drawer)
  if (wasDrawer !== drawer) {
    setWasDrawer(drawer)
    setOpenOn(null)
  }
  const menuOpen = drawer && openOn === pathname
  const closeMenu = () => setOpenOn(null)

  // Each new page starts at the top
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Skip to main content
      </a>
      <Sidebar id={SIDEBAR_ID} drawer={drawer} open={menuOpen} onClose={closeMenu} />
      {menuOpen && <div className="sidebar-scrim" onClick={closeMenu} aria-hidden />}

      <div className="app-main" inert={menuOpen}>
        <Topbar onMenu={() => setOpenOn(pathname)} menuOpen={menuOpen} menuControls={SIDEBAR_ID} />
        <main className="app-content" id="main" tabIndex={-1}>
          {/* Pages are lazy-loaded; keep the shell visible while a page chunk loads */}
          <RouteErrorBoundary key={pathname}>
            <Suspense fallback={<Loader />}>
              <Outlet />
            </Suspense>
          </RouteErrorBoundary>
        </main>
        <footer className="app-footer">
          <span className="app-footer__left">
            <Leaf size={18} className="app-footer__leaf" />
            {FOOTER_SLOGANS[pathname] ?? 'Good Food. Good Health. A Better Tomorrow.'}
            <span className="app-footer__sep">|</span>
            <strong>HIPA MASALA</strong>
          </span>
          <span>Pure Spices. A Better Tomorrow.</span>
        </footer>
      </div>
    </div>
  )
}
