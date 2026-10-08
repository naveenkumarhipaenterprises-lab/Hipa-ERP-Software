import { CalendarCheck } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { attendanceApi } from '../../api/attendanceApi'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import { useApi } from '../../hooks/useApi'
import { NAV_ITEMS } from '../../utils/constants'
import CalendarPanel from './components/CalendarPanel'
import EmployeesPanel from './components/EmployeesPanel'
import LeavePanel from './components/LeavePanel'
import ReportsPanel from './components/ReportsPanel'
import SettingsPanel from './components/SettingsPanel'
import TodayPanel from './components/TodayPanel'

// Exactly the sidebar sub-menu: Attendance, Employees, Leave / Permission, Calendar, Reports, Settings
const TABS = NAV_ITEMS.find((n) => n.key === 'attendance').children

/** Attendance. What each person can do comes from their Attendance permissions (checked again by the server). */
export default function AttendancePage() {
  const [params, setParams] = useSearchParams()
  const [refreshKey, setRefreshKey] = useState(0)
  const tab = TABS.some((t) => t.tab === params.get('tab')) ? params.get('tab') : TABS[0].tab
  const options = useApi(() => attendanceApi.getOptions(), [refreshKey])
  const refresh = () => setRefreshKey((k) => k + 1)
  const selectTab = (key) => setParams(key === TABS[0].tab ? {} : { tab: key }, { replace: true })
  const props = { options, refreshKey, onChanged: refresh }

  return (
    <div className="page">
      <title>Attendance | HIPA MASALA</title>
      <PageHeader icon={CalendarCheck} title="Attendance" subtitle="Check in and out, employees, leave and permission" />

      <div className="tabs" role="tablist" aria-label="Attendance sections">
        {TABS.map((t) => (
          <button
            key={t.tab}
            type="button"
            role="tab"
            id={`attendance-tab-${t.tab}`}
            aria-selected={tab === t.tab}
            aria-controls="attendance-tabpanel"
            className={`tabs__tab ${tab === t.tab ? 'tabs__tab--active' : ''}`}
            tabIndex={tab === t.tab ? 0 : -1}
            onClick={() => selectTab(t.tab)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = TABS.findIndex((x) => x.tab === tab)
              const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length].tab
              selectTab(next)
              document.getElementById(`attendance-tab-${next}`)?.focus()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack" role="tabpanel" id="attendance-tabpanel" aria-labelledby={`attendance-tab-${tab}`}>
        {options.error && !options.data && tab !== 'attendance' && <ErrorMessage message={options.error.message} onRetry={options.reload} />}
        {tab === 'attendance' && <TodayPanel />}
        {tab === 'employees' && <EmployeesPanel {...props} />}
        {tab === 'leave' && <LeavePanel {...props} />}
        {tab === 'calendar' && <CalendarPanel {...props} />}
        {tab === 'reports' && <ReportsPanel {...props} />}
        {tab === 'settings' && <SettingsPanel {...props} />}
      </div>
    </div>
  )
}
