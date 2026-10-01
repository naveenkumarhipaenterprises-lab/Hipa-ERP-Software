import { Bell, Building2, DatabaseBackup, History, Link2, Settings, ShieldCheck, Users } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { settingsApi } from '../../api/settingsApi'
import PageHeader from '../../components/common/PageHeader'
import { useApi } from '../../hooks/useApi'
import AuditSection from './sections/AuditSection'
import BackupSection from './sections/BackupSection'
import CompanySection from './sections/CompanySection'
import GeneralSection from './sections/GeneralSection'
import IntegrationsSection from './sections/IntegrationsSection'
import NotificationsSection from './sections/NotificationsSection'
import SecuritySection from './sections/SecuritySection'
import UsersSection from './sections/UsersSection'

const SECTIONS = [
  { key: 'general', label: 'General', icon: Settings, Component: GeneralSection },
  { key: 'company', label: 'Company Profile', icon: Building2, Component: CompanySection },
  { key: 'users', label: 'Users', icon: Users, Component: UsersSection },
  { key: 'notifications', label: 'Notifications', icon: Bell, Component: NotificationsSection },
  { key: 'backup', label: 'Data & Backup', icon: DatabaseBackup, Component: BackupSection },
  { key: 'integrations', label: 'Integrations', icon: Link2, Component: IntegrationsSection },
  { key: 'security', label: 'Security', icon: ShieldCheck, Component: SecuritySection },
  { key: 'audit', label: 'Audit Logs', icon: History, Component: AuditSection },
]

export default function SettingsPage() {
  const [params, setParams] = useSearchParams()
  const options = useApi(() => settingsApi.getOptions(), [])
  // ?section=users etc. so each section has its own address (and survives a refresh)
  const active = SECTIONS.find((s) => s.key === params.get('section')) ?? SECTIONS[0]
  const Section = active.Component

  return (
    <div className="page">
      <title>{`${active.label} | Settings | HIPA MASALA`}</title>
      <PageHeader icon={Settings} title="Settings" subtitle="Manage your business preferences, users, and system configuration" />

      <div className="settings-layout">
        <nav className="settings-nav card" aria-label="Settings sections">
          {SECTIONS.map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              type="button"
              className={`settings-nav__item ${active.key === key ? 'settings-nav__item--active' : ''}`}
              aria-current={active.key === key ? 'page' : undefined}
              onClick={() => setParams(key === 'general' ? {} : { section: key }, { replace: true })}
            >
              <Icon size={18} aria-hidden />
              {label}
            </button>
          ))}
        </nav>

        <div className="stack settings-content">
          {/* key: each section starts fresh when you switch to it */}
          <Section key={active.key} options={options} />
        </div>
      </div>
    </div>
  )
}
