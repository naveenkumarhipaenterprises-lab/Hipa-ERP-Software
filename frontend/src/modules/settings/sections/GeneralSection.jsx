import { settingsApi } from '../../../api/settingsApi'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import SettingsForm from '../components/SettingsForm'

const list = (v) => (Array.isArray(v) ? v : [])

/** Company-wide basics. Every choice list comes from GET /settings/options/. */
export default function GeneralSection({ options }) {
  const o = options.data ?? {}
  // Without the choice lists the drop-downs would be blank, so wait for them
  if (!options.data) {
    return (
      <Card title="General Settings" subtitle="Basic configuration for the whole portal">
        {options.error && !options.loading ? (
          <ErrorMessage message={options.error.message} onRetry={options.reload} />
        ) : (
          <div className="skeleton skeleton--list" aria-label="Loading" />
        )}
      </Card>
    )
  }
  return (
    <SettingsForm
      title="General Settings"
      subtitle="Basic configuration for the whole portal"
      load={settingsApi.getGeneral}
      save={settingsApi.saveGeneral}
      fields={[
        { name: 'company_name', label: 'Company name', required: true },
        { name: 'tagline', label: 'Tagline' },
        { name: 'timezone', label: 'Time zone', type: 'select', required: true, options: list(o.timezones) },
        { name: 'date_format', label: 'Date format', type: 'select', required: true, options: list(o.date_formats) },
        { name: 'time_format', label: 'Time format', type: 'select', required: true, options: list(o.time_formats) },
        { name: 'currency', label: 'Currency', type: 'select', required: true, options: list(o.currencies) },
        { name: 'language', label: 'Language', type: 'select', required: true, options: list(o.languages) },
      ]}
    />
  )
}
