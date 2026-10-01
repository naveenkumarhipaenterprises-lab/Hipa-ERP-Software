import { Megaphone, Search, Square } from 'lucide-react'
import { useState } from 'react'
import { marketingApi } from '../../../api/marketingApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber } from '../../../utils/formatters'

const PAGE_SIZE = 8
const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

/** Campaigns (server-paginated) with search, status filter and "End campaign" (confirmed). */
export default function CampaignsTable({ refreshKey, statuses, platforms, canManage, onChanged }) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [ending, setEnding] = useState(null)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, status]))

  const campaigns = useApi(() => marketingApi.listCampaigns({ page, page_size: PAGE_SIZE, search: query, status }), [page, query, status, refreshKey])
  const rows = list(campaigns.data?.results)
  const total = Number(campaigns.data?.count) || 0
  const filtered = Boolean(query || status)
  const platformLabel = (v) => list(platforms).find((p) => p.value === v)?.label ?? v

  const endCampaign = async () => {
    await marketingApi.endCampaign(ending.id)
    toast.success(`Campaign "${ending.name}" ended`)
    onChanged?.()
  }

  const columns = [
    { key: 'name', header: 'Campaign', render: (r) => <strong>{r.name}</strong> },
    { key: 'platform', header: 'Platform', render: (r) => (r.platform ? platformLabel(r.platform) : '—') },
    {
      key: 'dates',
      header: 'Dates',
      render: (r) => (
        <span className="nowrap">
          {r.start_date ? formatDate(r.start_date) : '—'} – {r.end_date ? formatDate(r.end_date) : '—'}
        </span>
      ),
    },
    { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
    { key: 'reach', header: 'Reach', align: 'right', render: (r) => (has(r.reach) ? formatNumber(r.reach) : '—') },
    { key: 'leads', header: 'Leads', align: 'right', render: (r) => (has(r.leads) ? formatNumber(r.leads) : '—') },
    { key: 'sales', header: 'Sales', align: 'right', render: (r) => (has(r.sales) ? formatINR(r.sales) : '—') },
  ]
  if (canManage) {
    columns.push({
      key: 'end',
      sticky: true,
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      render: (r) =>
        r.can_end === true && (
          <Button variant="ghost" size="sm" icon={Square} className="btn--tone-red" onClick={() => setEnding(r)}>
            End
          </Button>
        ),
    })
  }

  return (
    <Card title="Campaigns" subtitle={campaigns.loading ? undefined : `${formatNumber(total)} campaign${total === 1 ? '' : 's'}`} bodyClassName="card__body--flush">
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search campaigns" aria-label="Search campaigns" />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          options={[{ value: '', label: 'All statuses' }, ...list(statuses)]}
        />
      </div>

      {campaigns.error && !campaigns.loading ? (
        <div className="card__pad">
          <ErrorMessage message={campaigns.error.message} onRetry={campaigns.reload} />
        </div>
      ) : (
        <Table
          loading={campaigns.loading}
          caption="Campaigns"
          data={rows}
          columns={columns}
          emptyIcon={Megaphone}
          emptyTitle={filtered ? 'No campaigns match your filters' : 'No campaigns yet'}
          emptyMessage={filtered ? 'Try a different search or status.' : 'Create a campaign to start tracking reach, leads and sales.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
        />
      )}

      <ConfirmDialog
        open={Boolean(ending)}
        onClose={() => setEnding(null)}
        onConfirm={endCampaign}
        danger
        title="End this campaign?"
        message={ending && `"${ending.name}" will stop running now. Its results so far are kept.`}
        confirmLabel="End Campaign"
        cancelLabel="Keep Running"
      />
    </Card>
  )
}
