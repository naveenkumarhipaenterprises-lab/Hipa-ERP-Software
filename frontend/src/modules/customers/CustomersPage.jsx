import { MapPin, Plus, Send, Store, Upload, Users } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { customersApi } from '../../api/customersApi'
import DonutChart from '../../components/charts/DonutChart'
import ProgressList from '../../components/charts/ProgressList'
import SeriesChart from '../../components/charts/SeriesChart'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import { Select } from '../../components/common/Input'
import PageHeader from '../../components/common/PageHeader'
import { InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES } from '../../utils/constants'
import { formatNumber, formatPercent } from '../../utils/formatters'
import CustomerDetailsModal from './components/CustomerDetailsModal'
import CustomerFormModal from './components/CustomerFormModal'
import CustomersTable from './components/CustomersTable'
import ImportCustomersModal from './components/ImportCustomersModal'
import SendOfferModal from './components/SendOfferModal'
import TopCustomers from './components/TopCustomers'

// Roles that may add, edit or import customers, and roles that may send offers (the backend enforces the same)
const CUSTOMER_EDITORS = ['admin', 'management', 'sales']
const OFFER_SENDERS = ['admin', 'management', 'marketing']

const GROWTH_PERIODS = [
  { value: 'last_12_months', label: 'Last 12 Months' },
  { value: 'last_6_months', label: 'Last 6 Months' },
]
const TYPE_TONES = ['blue', 'red', 'orange', 'purple', 'teal', 'yellow']

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

export default function CustomersPage() {
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [type, setType] = useState('')
  const [period, setPeriod] = useState(GROWTH_PERIODS[0].value)
  const [modal, setModal] = useState(null) // 'import' | 'offer'
  const [editing, setEditing] = useState(null) // customer being edited
  const [viewing, setViewing] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const canEdit = CUSTOMER_EDITORS.includes(user?.role)
  const canOffer = OFFER_SENDERS.includes(user?.role)
  // ?new=customer (from the dashboard or the New Order form) opens the add form
  const adding = canEdit && params.get('new') === 'customer'

  const overview = useApi(() => customersApi.getOverview({ range, type }), [range, type, refreshKey])
  const growth = useApi(() => customersApi.getGrowth({ period, type }), [period, type, refreshKey])
  const options = useApi(() => customersApi.getOptions(), [])

  // Never show figures from another filter or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null

  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''
  const types = list(options.data?.types)
  const byType = list(data?.kpis?.by_type)
  const distribution = list(data?.type_distribution).map((d) => ({ name: d.name, value: Number(d.value) || 0 }))
  const distributionTotal = distribution.reduce((s, d) => s + d.value, 0)
  const locations = list(data?.locations).map((l) => ({ name: l.city, value: Number(l.customers) || 0 }))
  const locationMax = Math.max(1, ...locations.map((l) => l.value))

  const refresh = () => setRefreshKey((k) => k + 1)
  const setNewParam = (on) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        if (on) next.set('new', 'customer')
        else next.delete('new')
        return next
      },
      { replace: true },
    )

  const saveCustomer = async (values) => {
    if (editing) {
      const updated = await customersApi.update(editing.id, values)
      toast.success(`${updated?.name ?? values.name} updated`)
      setViewing((v) => (v && v.id === editing.id ? { ...v, ...values, ...updated } : v))
    } else {
      const created = await customersApi.create(values)
      toast.success(`${created?.name ?? values.name} added`)
    }
    refresh()
  }

  const actions = [
    ...(canEdit
      ? [
          { label: 'Add Customer', icon: Plus, tone: 'purple', onClick: () => setNewParam(true) },
          { label: 'Import List', icon: Upload, tone: 'blue', onClick: () => setModal('import') },
        ]
      : []),
    ...(canOffer ? [{ label: 'Send Offers', icon: Send, tone: 'green', onClick: () => setModal('offer') }] : []),
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
    <div className="page">
      <title>Customers | HIPA MASALA</title>
      <PageHeader icon={Users} title="Customers" subtitle="Build stronger relationships. Grow together.">
        <DateRangeSelect value={range} onChange={setRange} />
        <Select
          className="field--inline"
          aria-label="Filter by customer type"
          value={type}
          onChange={(e) => setType(e.target.value)}
          disabled={types.length === 0}
          options={[{ value: '', label: 'All Customer Types' }, ...types]}
        />
        {canEdit && (
          <Button icon={Plus} onClick={() => setNewParam(true)}>
            Add Customer
          </Button>
        )}
      </PageHeader>

      {failed && <ErrorMessage message={overview.error.message} onRetry={refresh} />}

      {!failed && (
        <>
          <div className="kpi-grid kpi-grid--auto">
            <StatCard
              icon={Users}
              tone="green"
              label="Total Customers"
              loading={loading}
              value={has(data?.kpis?.total?.value) ? formatNumber(data.kpis.total.value) : null}
              change={data?.kpis?.total?.change}
              changeLabel="vs prev. period"
            />
            {byType.map((t, i) => (
              <StatCard
                key={t.type}
                icon={Store}
                tone={TYPE_TONES[i % TYPE_TONES.length]}
                label={t.label || t.type}
                value={has(t.value) ? formatNumber(t.value) : null}
                change={t.change}
                changeLabel="vs prev. period"
              />
            ))}
          </div>

          <div className="dash-row">
            <Card
              title="Customer Growth"
              subtitle="Total customers"
              className="dash-row__wide"
              action={<MiniSelect label="Growth period" value={period} onChange={setPeriod} options={GROWTH_PERIODS} />}
            >
              {growth.loading ? (
                skeleton
              ) : growth.error ? (
                <ErrorMessage message={growth.error.message} onRetry={growth.reload} />
              ) : (
                <SeriesChart
                  data={list(growth.data)}
                  xKey="label"
                  series={[{ key: 'customers', name: 'Customers', color: 'var(--green-600)', type: 'area', dots: true }]}
                  yFormatter={formatNumber}
                  height={240}
                  emptyTitle="No customer history yet"
                  emptyMessage="Growth will appear as customers are added over time."
                />
              )}
            </Card>
            <Card title="Customer Type Distribution">
              {loading ? (
                skeleton
              ) : (
                <DonutChart
                  data={distribution}
                  colors={CHART_COLORS}
                  valueFormatter={(v) => formatNumber(v)}
                  legendValue={(d) => (distributionTotal ? formatPercent((d.value / distributionTotal) * 100, 1) : '—')}
                  centerValue={formatNumber(distributionTotal)}
                  centerLabel="Customers"
                  size={170}
                  emptyTitle="No customers yet"
                  emptyMessage="The split by customer type will appear here."
                />
              )}
            </Card>
            <Card title="Customer Locations" subtitle="Customers by city">
              {loading ? (
                skeleton
              ) : (
                <ProgressList
                  items={locations.slice(0, 8).map((l, i) => ({
                    ...l,
                    icon: <MapPin size={16} className="muted" aria-hidden />,
                    color: CHART_COLORS[i % CHART_COLORS.length],
                  }))}
                  max={locationMax}
                  format={formatNumber}
                  emptyTitle="No locations yet"
                  emptyMessage="Cities will appear once customers have addresses."
                />
              )}
            </Card>
          </div>

          <div className="grid-main-side">
            <CustomersTable type={type} refreshKey={refreshKey} statuses={options.data?.statuses} onView={setViewing} />
            <div className="stack">
              <Card title="Top Customers" subtitle={rangeLabel}>
                {loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <TopCustomers items={data?.top_customers} />}
              </Card>
              <InsightPanel
                title="Customer Insights"
                items={loading ? undefined : list(data?.insights).filter((s) => typeof s === 'string' && s.trim())}
                emptyText={loading ? 'Loading insights…' : undefined}
              />
              {actions.length > 0 && (
                <Card title="Quick Actions">
                  <QuickActions actions={actions} columns={actions.length > 2 ? 3 : actions.length} layout="stack" />
                </Card>
              )}
            </div>
          </div>
        </>
      )}

      <CustomerFormModal
        open={adding || Boolean(editing)}
        customer={editing}
        options={options}
        onClose={() => {
          setEditing(null)
          setNewParam(false)
        }}
        onSave={saveCustomer}
      />
      <CustomerDetailsModal
        customer={editing ? null : viewing}
        onClose={() => setViewing(null)}
        onEdit={canEdit ? (c) => setEditing(c) : undefined}
      />
      <ImportCustomersModal open={modal === 'import'} onClose={() => setModal(null)} onImported={refresh} />
      <SendOfferModal open={modal === 'offer'} options={options} onClose={() => setModal(null)} />
    </div>
  )
}
