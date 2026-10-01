import { settingsApi } from '../../../api/settingsApi'
import { isGstin, isUrl } from '../../../utils/validation'
import SettingsForm from '../components/SettingsForm'

/** Business details printed on quotations, invoices and reports. */
export default function CompanySection() {
  return (
    <SettingsForm
      title="Company Profile"
      subtitle="Your registered business information"
      load={settingsApi.getCompany}
      save={(values) => settingsApi.saveCompany({ ...values, gstin: values.gstin.toUpperCase(), phone: values.phone.replace(/[\s-]/g, '') })}
      successMessage="Company profile saved"
      fields={[
        { name: 'legal_name', label: 'Registered name', required: true, full: true },
        { name: 'address', label: 'Address', type: 'textarea', required: true },
        { name: 'email', label: 'Email', type: 'email', required: true },
        { name: 'phone', label: 'Phone', type: 'tel', required: true, placeholder: '10-digit mobile number' },
        { name: 'website', label: 'Website', placeholder: 'https://…', validate: (v) => (!isUrl(v) ? 'Enter a full address starting with https://' : undefined) },
        { name: 'gstin', label: 'GSTIN', placeholder: '15-character GST number', validate: (v) => (!isGstin(v) ? 'Enter a valid 15-character GSTIN' : undefined) },
      ]}
    />
  )
}
