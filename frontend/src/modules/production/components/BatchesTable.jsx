import { Factory, Plus } from 'lucide-react'
import { useState } from 'react'
import { productionApi } from '../../../api/productionApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatKg } from '../../../utils/formatters'

const PAGE_SIZE = 10
const list = (v) => (Array.isArray(v) ? v : [])

/** Scheduled and in-progress batches (server-paginated), with stage updates for allowed roles. */
export default function BatchesTable({ refreshKey, stages, canManage, onNew, onChanged }) {
  const toast = useToast()
  const [stage, setStage] = useState('')
  const [updating, setUpdating] = useState(null)
  const [page, setPage] = usePageReset(stage)

  const batches = useApi(() => productionApi.listBatches({ page, page_size: PAGE_SIZE, stage }), [page, stage, refreshKey])
  const rows = list(batches.data?.results)
  const total = Number(batches.data?.count) || 0
  const stageLabel = (value) => list(stages).find((s) => s.value === value)?.label ?? value

  const saveStage = async ({ stage: next }) => {
    await productionApi.updateBatch(updating.id, { stage: next })
    toast.success(`Batch ${updating.batch_number ?? updating.id} moved to ${stageLabel(next)}`)
    onChanged?.()
  }

  const columns = [
    { key: 'batch_number', header: 'Batch ID', render: (r) => <strong>{r.batch_number ?? r.id}</strong> },
    { key: 'product', header: 'Product' },
    { key: 'quantity_kg', header: 'Quantity', align: 'right', render: (r) => (r.quantity_kg != null ? formatKg(r.quantity_kg) : '—') },
    { key: 'line', header: 'Line', render: (r) => r.line || '—' },
    { key: 'start_date', header: 'Start', render: (r) => <span className="nowrap">{r.start_date ? formatDate(r.start_date) : '—'}</span> },
    { key: 'due_date', header: 'Due', render: (r) => <span className="nowrap">{r.due_date ? formatDate(r.due_date) : '—'}</span> },
    { key: 'stage', header: 'Stage', render: (r) => (r.stage ? <Badge>{stageLabel(r.stage)}</Badge> : '—') },
  ]
  if (canManage) {
    columns.push({
      key: 'update',
      sticky: true,
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (r) =>
        r.can_update === true && list(stages).length > 0 && (
          <Button size="sm" variant="soft" onClick={() => setUpdating(r)}>
            Update Stage
          </Button>
        ),
    })
  }

  return (
    <Card
      title="Production Batches"
      subtitle="Scheduled and in-progress batches"
      bodyClassName="card__body--flush"
      action={
        canManage && (
          <Button size="sm" icon={Plus} onClick={onNew}>
            New Batch
          </Button>
        )
      }
    >
      <div className="toolbar">
        <Select
          className="field--inline"
          aria-label="Filter by stage"
          value={stage}
          onChange={(e) => setStage(e.target.value)}
          options={[{ value: '', label: 'All stages' }, ...list(stages)]}
        />
      </div>

      {batches.error && !batches.loading ? (
        <div className="card__pad">
          <ErrorMessage message={batches.error.message} onRetry={batches.reload} />
        </div>
      ) : (
        <Table
          loading={batches.loading}
          caption="Production batches"
          data={rows}
          columns={columns}
          emptyIcon={Factory}
          emptyTitle={stage ? 'No batches at this stage' : 'No production batches yet'}
          emptyMessage={stage ? 'Try another stage.' : 'Scheduled batches will be listed here.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}

      <FormModal
        open={Boolean(updating)}
        onClose={() => setUpdating(null)}
        title="Update Stage"
        subtitle={updating ? `Batch ${updating.batch_number ?? updating.id} • ${updating.product ?? ''}` : ''}
        submitLabel="Update"
        initialValues={{ stage: updating?.stage ?? '' }}
        fields={[{ name: 'stage', label: 'Stage', type: 'select', required: true, options: list(stages), full: true }]}
        onSubmit={saveStage}
      />
    </Card>
  )
}
