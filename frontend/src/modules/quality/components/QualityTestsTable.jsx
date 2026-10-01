import { FlaskConical, Search } from 'lucide-react'
import { useState } from 'react'
import { qualityApi } from '../../../api/qualityApi'
import Badge from '../../../components/common/Badge'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import { Select } from '../../../components/common/Input'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { useDebouncedValue } from '../../../hooks/useDebouncedValue'
import { usePageReset } from '../../../hooks/usePageReset'
import { formatDate, formatNumber } from '../../../utils/formatters'

const PAGE_SIZE = 10

/** Quality test results: server-side search, result filter and pagination, with a details view. */
export default function QualityTestsTable({ refreshKey, results }) {
  const [search, setSearch] = useState('')
  const [result, setResult] = useState('')
  const [viewing, setViewing] = useState(null)
  const query = useDebouncedValue(search.trim())
  const [page, setPage] = usePageReset(JSON.stringify([query, result]))

  const tests = useApi(() => qualityApi.listTests({ page, page_size: PAGE_SIZE, search: query, result }), [page, query, result, refreshKey])
  const rows = Array.isArray(tests.data?.results) ? tests.data.results : []
  const total = Number(tests.data?.count) || 0
  const filtered = Boolean(query || result)

  return (
    <Card
      title="Quality Test Results"
      subtitle={tests.loading ? undefined : `${formatNumber(total)} test${total === 1 ? '' : 's'}`}
      bodyClassName="card__body--flush"
    >
      <div className="toolbar">
        <label className="toolbar__search">
          <Search size={16} aria-hidden />
          <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search lot, item or GRN" aria-label="Search tests" />
        </label>
        <Select
          className="field--inline"
          aria-label="Filter by result"
          value={result}
          onChange={(e) => setResult(e.target.value)}
          options={[{ value: '', label: 'All results' }, ...(Array.isArray(results) ? results : [])]}
        />
      </div>

      {tests.error && !tests.loading ? (
        <div className="card__pad">
          <ErrorMessage message={tests.error.message} onRetry={tests.reload} />
        </div>
      ) : (
        <Table
          loading={tests.loading}
          caption="Quality test results"
          data={rows}
          emptyIcon={FlaskConical}
          emptyTitle={filtered ? 'No tests match your filters' : 'No test results yet'}
          emptyMessage={filtered ? 'Try a different search or result.' : 'Lab results appear here once lots are tested.'}
          pagination={{ page, pageSize: PAGE_SIZE, total, onPageChange: setPage }}
          columns={[
            {
              key: 'product',
              header: 'Item',
              render: (r) => (
                <button type="button" className="link link--strong table-link" onClick={() => setViewing(r)}>
                  {r.product || `Test ${r.id}`}
                </button>
              ),
            },
            { key: 'batch_number', header: 'Lot / Batch', render: (r) => r.batch_number || '—' },
            { key: 'grn_number', header: 'GRN', render: (r) => r.grn_number || '—' },
            { key: 'test_date', header: 'Test Date', render: (r) => <span className="nowrap">{r.test_date ? formatDate(r.test_date) : '—'}</span> },
            { key: 'parameters', header: 'Parameters', render: (r) => <span className="cell-clip">{r.parameters || '—'}</span> },
            { key: 'result', header: 'Result', render: (r) => (r.result ? <Badge>{r.result}</Badge> : '—') },
            { key: 'status', header: 'Status', render: (r) => (r.status ? <Badge>{r.status}</Badge> : '—') },
          ]}
        />
      )}

      <Modal open={Boolean(viewing)} onClose={() => setViewing(null)} title={viewing?.product ?? 'Quality test'}
             subtitle={[viewing?.batch_number && `Lot ${viewing.batch_number}`, viewing?.grn_number].filter(Boolean).join(' · ') || undefined}>
        {viewing && (
          <dl className="detail-list">
            <dt>Test date</dt>
            <dd>{viewing.test_date ? formatDate(viewing.test_date) : '—'}</dd>
            <dt>Parameters</dt>
            <dd>{viewing.parameters || '—'}</dd>
            <dt>Result</dt>
            <dd>{viewing.result ? <Badge>{viewing.result}</Badge> : '—'}</dd>
            <dt>Status</dt>
            <dd>{viewing.status ? <Badge>{viewing.status}</Badge> : '—'}</dd>
            <dt>Notes</dt>
            <dd>{viewing.notes || '—'}</dd>
          </dl>
        )}
      </Modal>
    </Card>
  )
}
