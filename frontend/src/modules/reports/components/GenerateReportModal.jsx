import FormModal from '../../../components/common/FormModal'
import { DATE_RANGES } from '../../../utils/constants'
import { EXPORT_FORMATS } from '../reportTypes'

/** Requests a report file from the backend (POST /reports/); it then appears under Recent Reports. */
export default function GenerateReportModal({ open, types, defaults, onClose, onGenerate }) {
  return (
    <FormModal
      open={open}
      onClose={onClose}
      title="Generate Report"
      subtitle="The file is prepared by the server and listed under Recent Reports"
      submitLabel="Generate"
      initialValues={defaults}
      fields={[
        { name: 'type', label: 'Report type', type: 'select', required: true, full: true, options: types.map((t) => ({ value: t.key, label: t.label })) },
        { name: 'range', label: 'Date range', type: 'select', required: true, options: DATE_RANGES },
        { name: 'format', label: 'Format', type: 'select', required: true, options: EXPORT_FORMATS },
      ]}
      onSubmit={onGenerate}
    />
  )
}
