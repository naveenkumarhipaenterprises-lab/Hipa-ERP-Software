import { ChartColumn, Pencil, Plus } from 'lucide-react'
import { useState } from 'react'
import { marketingApi } from '../../../api/marketingApi'
import Button from '../../../components/common/Button'
import DeleteRecordButton from '../../../components/common/DeleteRecordButton'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import ListToolbar from '../../../components/common/ListToolbar'
import Modal from '../../../components/common/Modal'
import Table from '../../../components/common/Table'
import { useApi } from '../../../hooks/useApi'
import { usePagedList } from '../../../hooks/usePagedList'
import { useToast } from '../../../hooks/useToast'
import { formatDate, formatINR, formatNumber, todayISO } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const notFuture = (label) => (v) => (v > todayISO() ? `The ${label} can't be in the future` : undefined)
const count = (name, label) => ({ name, label, type: 'number', min: 0 })
const date = (v) => <span className="nowrap">{formatDate(v)}</span>

/**
 * One kind of marketing data: what the list shows, the form, and how a row is saved / deleted.
 * Numbers come from each platform's own analytics (Instagram Insights, YouTube Studio, Google Analytics, …).
 */
function kinds({ platforms, campaigns }) {
  return {
    metrics: {
      tab: 'Daily Numbers',
      what: 'daily numbers',
      hint: 'One row per day and platform (and campaign, if any). They make up Reach, Engagement, Visitors, Leads and Sales on the dashboard.',
      list: marketingApi.listMetrics,
      save: marketingApi.saveMetric,
      deleteKind: 'marketing_metric',
      label: (r) => `${r.platform} ${formatDate(r.date)}`,
      search: 'Search campaign',
      columns: [
        { key: 'date', header: 'Date', render: (r) => date(r.date) },
        { key: 'platform', header: 'Platform' },
        { key: 'campaign', header: 'Campaign', render: (r) => r.campaign || '—' },
        { key: 'reach', header: 'Reach', align: 'right', render: (r) => formatNumber(r.reach) },
        { key: 'engagement', header: 'Engagement', align: 'right', render: (r) => formatNumber(r.engagement) },
        { key: 'website_visitors', header: 'Visitors', align: 'right', render: (r) => formatNumber(r.website_visitors) },
        { key: 'leads', header: 'Leads', align: 'right', render: (r) => formatNumber(r.leads) },
        { key: 'sales_amount', header: 'Sales', align: 'right', render: (r) => formatINR(r.sales_amount) },
      ],
      fields: [
        { name: 'date', label: 'Date', type: 'date', required: true, validate: notFuture('date') },
        { name: 'platform', label: 'Platform', type: 'select', required: true, options: platforms, placeholder: 'Select platform' },
        { name: 'campaign_id', label: 'Campaign (optional)', type: 'select', full: true, placeholder: 'No campaign',
          options: campaigns.map((c) => ({ value: String(c.id), label: `${c.name} (${c.platform})` })) },
        count('reach', 'Reach'), count('engagement', 'Engagement'), count('website_visitors', 'Website visitors'), count('leads', 'Leads'),
        { name: 'sales_amount', label: 'Sales (₹)', type: 'number', min: 0 },
      ],
      initial: (r) => (r ? { date: r.date, platform: r.platform_value, campaign_id: r.campaign_id ? String(r.campaign_id) : '',
        reach: r.reach, engagement: r.engagement, website_visitors: r.website_visitors, leads: r.leads, sales_amount: r.sales_amount }
        : { date: todayISO() }),
    },
    content: {
      tab: 'Content',
      what: 'content',
      hint: 'Posts, reels and videos with their views, likes and shares. The most viewed show under Top Content.',
      list: marketingApi.listContent,
      save: marketingApi.saveContent,
      deleteKind: 'content_item',
      label: (r) => r.title,
      search: 'Search title',
      columns: [
        { key: 'published_on', header: 'Published', render: (r) => date(r.published_on) },
        { key: 'title', header: 'Title', render: (r) => (r.url ? <a className="link" href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> : r.title) },
        { key: 'platform', header: 'Platform' },
        { key: 'views', header: 'Views', align: 'right', render: (r) => formatNumber(r.views) },
        { key: 'likes', header: 'Likes', align: 'right', render: (r) => formatNumber(r.likes) },
        { key: 'shares', header: 'Shares', align: 'right', render: (r) => formatNumber(r.shares) },
      ],
      fields: [
        { name: 'title', label: 'Title', required: true, full: true, placeholder: 'e.g. Sambar Powder recipe reel' },
        { name: 'platform', label: 'Platform', type: 'select', required: true, options: platforms, placeholder: 'Select platform' },
        { name: 'published_on', label: 'Published on', type: 'date', required: true, validate: notFuture('published date') },
        count('views', 'Views'), count('likes', 'Likes'), count('shares', 'Shares'),
        { name: 'url', label: 'Link (optional)', full: true, placeholder: 'https://…' },
      ],
      initial: (r) => (r ? { title: r.title, platform: r.platform_value, published_on: r.published_on, views: r.views, likes: r.likes,
        shares: r.shares, url: r.url ?? '' } : { published_on: todayISO() }),
    },
    audience: {
      tab: 'Audience',
      what: 'audience figure',
      hint: 'Audience split as each platform reports it, e.g. age 25-34 = 38%. The latest date per platform is shown on the dashboard.',
      list: marketingApi.listSegments,
      save: marketingApi.saveSegment,
      deleteKind: 'audience_segment',
      label: (r) => `${r.platform} ${r.name}`,
      search: 'Search audience group',
      columns: [
        { key: 'as_of', header: 'As of', render: (r) => date(r.as_of) },
        { key: 'platform', header: 'Platform' },
        { key: 'name', header: 'Audience group' },
        { key: 'value', header: 'Share', align: 'right', render: (r) => `${formatNumber(r.value)}%` },
      ],
      fields: [
        { name: 'platform', label: 'Platform', type: 'select', required: true, options: platforms, placeholder: 'Select platform' },
        { name: 'name', label: 'Audience group', required: true, placeholder: 'e.g. 25-34, Women, Chennai' },
        { name: 'value', label: 'Share of audience (%)', type: 'number', min: 0, required: true,
          validate: (v) => (Number(v) > 100 ? 'A share can be at most 100%' : undefined) },
        { name: 'as_of', label: 'As of', type: 'date', required: true, validate: notFuture('date') },
      ],
      initial: (r) => (r ? { platform: r.platform_value, name: r.name, value: r.value, as_of: r.as_of } : { as_of: todayISO() }),
    },
  }
}

function DataTab({ kind, platforms, canManage, onChanged }) {
  const toast = useToast()
  const [form, setForm] = useState(null) // { row? }
  const [refresh, setRefresh] = useState(0)
  const l = usePagedList(kind.list, { platform: '' }, refresh)
  const changed = () => {
    setRefresh((k) => k + 1)
    onChanged?.()
  }
  const save = async (values) => {
    const saved = await kind.save(form.row?.id, values)
    toast.success(form.row ? `${kind.label(saved)} updated` : `${kind.label(saved)} added`)
    changed()
  }
  const columns = [...kind.columns, ...(canManage ? [{
    key: 'actions', sticky: true, align: 'right', header: <span className="sr-only">Actions</span>,
    render: (r) => (
      <span className="row-actions">
        <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setForm({ row: r })} aria-label={`Edit ${kind.label(r)}`} />
        <DeleteRecordButton kind={kind.deleteKind} id={r.id} label={kind.label(r)} onDeleted={changed} />
      </span>
    ),
  }] : [])]

  return (
    <div className="stack">
      <p className="muted">{kind.hint}</p>
      <div className="toolbar toolbar--flush">
        <ListToolbar search={l.search} onSearch={l.setSearch} searchLabel={kind.search} onFilter={l.setFilter}
                     filters={[{ name: 'platform', label: 'Filter by platform', value: l.filters.platform,
                                 options: [{ value: '', label: 'All platforms' }, ...platforms] }]} />
        {canManage && <Button size="sm" icon={Plus} onClick={() => setForm({})}>Add {kind.what}</Button>}
      </div>
      {l.result.error && !l.result.loading ? (
        <ErrorMessage message={l.result.error.message} onRetry={l.result.reload} />
      ) : (
        <Table
          compact
          loading={l.result.loading}
          caption={kind.tab}
          data={l.rows}
          columns={columns}
          emptyIcon={ChartColumn}
          emptyTitle={l.filtered ? `No ${kind.what} match` : `No ${kind.what} entered yet`}
          emptyMessage={l.filtered ? 'Try another search or platform.' : 'Copy the figures from the platform\'s analytics.'}
          pagination={{ page: l.page, pageSize: l.pageSize, total: l.total, onPageChange: l.setPage }}
        />
      )}
      <FormModal
        open={Boolean(form)}
        onClose={() => setForm(null)}
        title={form?.row ? `Edit ${kind.label(form.row)}` : `Add ${kind.what}`}
        subtitle="Figures from the platform's own analytics"
        fields={kind.fields}
        initialValues={kind.initial(form?.row)}
        submitLabel="Save"
        onSubmit={save}
      />
    </div>
  )
}

/** Marketing → Enter Data: the numbers behind the Marketing dashboard, entered by the team. */
export default function MarketingDataModal({ open, options, canManage, onClose, onChanged }) {
  if (!open) return null
  return <MarketingData options={options} canManage={canManage} onClose={onClose} onChanged={onChanged} />
}

function MarketingData({ options, canManage, onClose, onChanged }) {
  const [tab, setTab] = useState('metrics')
  const campaigns = useApi(() => marketingApi.listCampaigns({ page_size: 100 }), [])
  const all = kinds({ platforms: list(options.data?.platforms), campaigns: list(campaigns.data?.results) })
  return (
    <Modal open onClose={onClose} title="Marketing Data" subtitle="Enter the figures from each platform's analytics" size="xl">
      {options.error && !options.data ? (
        <ErrorMessage message={options.error.message} onRetry={options.reload} />
      ) : (
        <div className="stack">
          <div className="tabs" role="tablist" aria-label="Marketing data">
            {Object.entries(all).map(([key, k]) => (
              <button key={key} type="button" role="tab" aria-selected={tab === key} className={`tabs__tab ${tab === key ? 'tabs__tab--active' : ''}`}
                      onClick={() => setTab(key)}>
                {k.tab}
              </button>
            ))}
          </div>
          <DataTab key={tab} kind={all[tab]} platforms={list(options.data?.platforms)} canManage={canManage} onChanged={onChanged} />
        </div>
      )}
    </Modal>
  )
}
