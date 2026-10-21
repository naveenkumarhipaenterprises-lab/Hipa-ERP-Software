import { settingsApi } from '../../../api/settingsApi'
import SettingsForm from '../components/SettingsForm'

/**
 * Company-wide basics. The portal works in India time (IST), DD/MM/YYYY dates and Indian Rupees; those are fixed,
 * so only the name and tagline are set here (the server keeps any older saved time zone / format values as they are).
 */
export default function GeneralSection() {
  return (
    <SettingsForm
      title="General Settings"
      subtitle="Company name and tagline. The portal uses India time (IST), DD/MM/YYYY dates and Indian Rupees (₹)."
      load={settingsApi.getGeneral}
      save={settingsApi.saveGeneral}
      fields={[
        { name: 'company_name', label: 'Company name', required: true },
        { name: 'tagline', label: 'Tagline' },
      ]}
    />
  )
}
