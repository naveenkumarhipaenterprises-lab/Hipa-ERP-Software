import { Menu, Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ScriptTagline from '../common/ScriptTagline'
import NotificationsMenu from './NotificationsMenu'
import UserMenu from './UserMenu'

const SEARCH_HINTS = {
  '/dashboard': 'Search products, orders, customers, suppliers...',
  '/sales': 'Search products, customers, orders...',
  '/inventory': 'Search products, batches, or reports...',
  '/purchase': 'Search purchases, suppliers, materials...',
  '/marketing': 'Search campaigns, posts, performance...',
  '/customers': 'Search customers, locations, orders, or contacts...',
  '/supply-chain': 'Search suppliers, orders, shipments, routes...',
  '/quality': 'Search batches, products, test reports...',
  '/attendance': 'Search employees, leave, attendance...',
  '/ai-assistant': 'Ask anything about sales, inventory, purchases, marketing...',
  '/reports': 'Search reports, sales, marketing, inventory, customers...',
  '/settings': 'Search settings, users, preferences, integrations...',
}

const isTyping = (el) => el?.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el?.tagName)

export default function Topbar({ onMenu, menuOpen = false, menuControls }) {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const [query, setQuery] = useState('')
  // A menu stays open only on the page where it was opened, so navigating closes it
  const [menu, setMenu] = useState({ name: null, path: null })
  const openMenu = menu.path === pathname ? menu.name : null
  const searchRef = useRef(null)

  const toggle = (name) => setMenu((m) => (m.name === name && m.path === pathname ? { name: null, path: null } : { name, path: pathname }))
  const close = () => setMenu({ name: null, path: null })

  // "/" or Ctrl/⌘+K jumps to search from anywhere
  useEffect(() => {
    const onKey = (e) => {
      const combo = (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k'
      if (combo || (e.key === '/' && !isTyping(document.activeElement))) {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const submitSearch = (e) => {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    // Free-text questions are answered by the AI Assistant
    navigate(`/ai-assistant?q=${encodeURIComponent(q)}`)
    setQuery('')
    searchRef.current?.blur()
  }

  return (
    <header className="topbar">
      <button
        className="icon-btn topbar__menu"
        onClick={onMenu}
        aria-label="Open menu"
        aria-expanded={menuOpen}
        aria-controls={menuControls}
      >
        <Menu size={22} />
      </button>

      <form className="topbar__search" onSubmit={submitSearch} role="search">
        <Search size={18} aria-hidden />
        <input
          ref={searchRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && e.currentTarget.blur()}
          placeholder={SEARCH_HINTS[pathname] ?? SEARCH_HINTS['/dashboard']}
          aria-label="Search or ask the AI assistant"
          aria-keyshortcuts="Control+K /"
          enterKeyHint="search"
        />
        <kbd className="topbar__kbd" aria-hidden>
          Ctrl K
        </kbd>
      </form>

      <div className="topbar__right">
        <NotificationsMenu open={openMenu === 'notes'} onToggle={() => toggle('notes')} onClose={close} />
        <span className="topbar__divider" aria-hidden />
        <UserMenu open={openMenu === 'user'} onToggle={() => toggle('user')} onClose={close} />
        <ScriptTagline className="topbar__tagline" />
      </div>
    </header>
  )
}
