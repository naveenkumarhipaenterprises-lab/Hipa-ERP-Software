import { ClipboardList } from 'lucide-react'
import { qualityApi } from '../../../api/qualityApi'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'

/** Acceptance limits applied to batches (GET /quality/standards/). */
export default function StandardsModal({ open, onClose }) {
  if (!open) return null
  return <Standards onClose={onClose} />
}

function Standards({ onClose }) {
  const standards = useApi(() => qualityApi.getStandards(), [])
  const rows = Array.isArray(standards.data) ? standards.data : []
  return (
    <Modal open onClose={onClose} title="Quality Standards" subtitle="Acceptance limits applied to every batch">
      {standards.error && !standards.loading ? (
        <ErrorMessage message={standards.error.message} onRetry={standards.reload} />
      ) : (
        <Table
          compact
          loading={standards.loading}
          caption="Quality standards"
          rowKey={(r, i) => r.id ?? i}
          data={rows}
          emptyIcon={ClipboardList}
          emptyTitle="No standards defined"
          emptyMessage="Acceptance limits are set up by the quality team in the system settings."
          columns={[
            { key: 'parameter', header: 'Parameter' },
            { key: 'limit', header: 'Limit' },
            { key: 'applies_to', header: 'Applies to', render: (r) => r.applies_to || 'All products' },
          ]}
        />
      )}
    </Modal>
  )
}
