import { ChartColumnBig, ChartPie, Database, IndianRupee, Minus, Plus, Receipt, Settings2, Wallet } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { financeApi } from '../../api/financeApi'
import DonutChart from '../../components/charts/DonutChart'
import SeriesChart from '../../components/charts/SeriesChart'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import Table from '../../components/common/Table'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES } from '../../utils/constants'
import { formatINR, formatINRShort, formatPercent } from '../../utils/formatters'
import BudgetCard from './components/BudgetCard'
import BudgetModal from './components/BudgetModal'
import LedgerModal from './components/LedgerModal'
import PendingPayments from './components/PendingPayments'
import { transactionColumns } from './components/transactionColumns'
import TransactionDetailsModal from './components/TransactionDetailsModal'
import TransactionModal from './components/TransactionModal'

// Roles that may record transactions and set budgets (the backend enforces the same rule)
const FINANCE_MANAGERS = ['admin', 'management', 'finance']

const GRANULARITY = [
  { value: 'monthly', label: 'Monthly' },
  { value: 'quarterly', label: 'Quarterly' },
]
const CASH_MONTHS = [
  { value: '6', label: 'Last 6 Months' },
  { value: '3', label: 'Last 3 Months' },
]

const KPIS = [
  { key: 'revenue', label: 'Total Revenue', icon: IndianRupee, tone: 'green', format: formatINR },
  { key: 'expenses', label: 'Total Expenses', icon: Wallet, tone: 'red', format: formatINR, goodWhenDown: true },
  { key: 'net_profit', label: 'Net Profit', icon: ChartColumnBig, tone: 'blue', format: formatINR },
  { key: 'profit_margin_pct', label: 'Profit Margin', icon: ChartPie, tone: 'yellow', format: (v) => formatPercent(v, 1) },
]

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''
const withTotal = (items) => {
  const rows = list(items).map((d) => ({ name: d.name, value: Number(d.value) || 0 }))
  const total = rows.reduce((s, d) => s + d.value, 0)
  return { rows, total, share: (d) => (total ? formatPercent((d.value / total) * 100, 1) : '—') }
}

export default function FinancePage() {
  const { user, can } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [granularity, setGranularity] = useState(GRANULARITY[0].value)
  const [months, setMonths] = useState(CASH_MONTHS[0].value)
  const [txType, setTxType] = useState(null) // 'income' | 'expense'
  const [modal, setModal] = useState(null) // 'budget' | 'ledger'
  const [viewing, setViewing] = useState(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const canManage = FINANCE_MANAGERS.includes(user?.role)
  const overview = useApi(() => financeApi.getOverview({ range }), [range, refreshKey])
  const revExp = useApi(() => financeApi.getRevenueExpenses({ granularity }), [granularity, refreshKey])
  const cashFlow = useApi(() => financeApi.getCashFlow({ months }), [months, refreshKey])
  const options = useApi(() => financeApi.getOptions(), [])

  // Never show figures from another range or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null
  const insights = data?.insights ?? {}
  const expenses = withTotal(data?.expense_breakdown)
  const income = withTotal(data?.income_sources)

  const refresh = () => setRefreshKey((k) => k + 1)

  const saveTransaction = async (values) => {
    await financeApi.createTransaction(values)
    toast.success(`${values.type === 'income' ? 'Income' : 'Expense'} of ${formatINR(values.amount)} recorded`)
    refresh()
  }

  const saveBudget = async (values) => {
    await financeApi.setBudget(values)
    toast.success('Budget saved')
    refresh()
  }

  const actions = [
    ...(canManage
      ? [
          { label: 'Record Income', icon: Plus, tone: 'green', onClick: () => setTxType('income') },
          { label: 'Record Expense', icon: Minus, tone: 'red', onClick: () => setTxType('expense') },
        ]
      : []),
    ...(can('reports') ? [{ label: 'Generate Report', icon: ChartColumnBig, tone: 'blue', onClick: () => navigate('/reports?type=finance') }] : []),
    ...(canManage ? [{ label: 'Set Budget', icon: Settings2, tone: 'purple', onClick: () => setModal('budget') }] : []),
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />
  const donut = (d, label, emptyTitle, emptyMessage) => (
    <DonutChart
      data={d.rows}
      colors={CHART_COLORS}
      valueFormatter={(v) => formatINR(v)}
      legendValue={d.share}
      centerValue={formatINRShort(d.total)}
      centerLabel={label}
      size={160}
      emptyTitle={emptyTitle}
      emptyMessage={emptyMessage}
    />
  )

  return (
    <div className="page">
      <title>Finance | HIPA MASALA</title>
      <PageHeader icon={Database} title="Finance" subtitle="Control Today. Grow Tomorrow.">
        <DateRangeSelect value={range} onChange={setRange} />
        {canManage && (
          <>
            <Button variant="outline" icon={Minus} onClick={() => setTxType('expense')}>
              Record Expense
            </Button>
            <Button icon={Plus} onClick={() => setTxType('income')}>
              Record Income
            </Button>
          </>
        )}
      </PageHeader>

      {failed && <ErrorMessage message={overview.error.message} onRetry={refresh} />}

      {!failed && (
        <>
          <div className="kpi-grid">
            {KPIS.map((k) => {
              const kpi = data?.kpis?.[k.key]
              return (
                <StatCard
                  key={k.key}
                  icon={k.icon}
                  tone={k.tone}
                  label={k.label}
                  loading={loading}
                  value={has(kpi?.value) ? k.format(kpi.value) : null}
                  change={kpi?.change}
                  changeLabel="vs prev. period"
                  goodWhenDown={k.goodWhenDown}
                  valueTone={k.key === 'net_profit' && Number(kpi?.value) < 0 ? 'red' : undefined}
                />
              )
            })}
          </div>

          <div className="dash-row">
            <Card
              title="Revenue vs Expenses"
              className="dash-row__wide"
              action={<MiniSelect label="Revenue vs expenses granularity" value={granularity} onChange={setGranularity} options={GRANULARITY} />}
            >
              {revExp.loading ? (
                skeleton
              ) : revExp.error ? (
                <ErrorMessage message={revExp.error.message} onRetry={revExp.reload} />
              ) : (
                <SeriesChart
                  data={list(revExp.data)}
                  xKey="label"
                  showLegend
                  series={[
                    { key: 'revenue', name: 'Revenue', color: '#1f9d55', type: 'bar' },
                    { key: 'expenses', name: 'Expenses', color: '#f07070', type: 'bar' },
                  ]}
                  yFormatter={formatINRShort}
                  tooltipFormatter={(v) => formatINR(v)}
                  height={250}
                  emptyTitle="No revenue or expenses recorded"
                  emptyMessage="The comparison appears once transactions are recorded."
                />
              )}
            </Card>
            <Card title="Expense Breakdown">{loading ? skeleton : donut(expenses, 'Expenses', 'No expenses yet', 'Spending by category will appear here.')}</Card>
            <Card title="Income Sources">{loading ? skeleton : donut(income, 'Revenue', 'No income yet', 'Revenue by source will appear here.')}</Card>
          </div>

          <div className="dash-row">
            <Card title="Recent Transactions" onViewAll={() => setModal('ledger')} bodyClassName="card__body--flush" className="dash-row__wide">
              <Table
                compact
                loading={loading}
                caption="Recent transactions"
                data={list(data?.recent_transactions)}
                columns={transactionColumns(setViewing)}
                emptyIcon={Receipt}
                emptyTitle="No transactions yet"
                emptyMessage="Recorded income and expenses will appear here."
              />
            </Card>
            <Card
              title="Cash Flow"
              className="dash-row__wide"
              action={<MiniSelect label="Cash flow period" value={months} onChange={setMonths} options={CASH_MONTHS} />}
            >
              {cashFlow.loading ? (
                skeleton
              ) : cashFlow.error ? (
                <ErrorMessage message={cashFlow.error.message} onRetry={cashFlow.reload} />
              ) : (
                <SeriesChart
                  data={list(cashFlow.data)}
                  xKey="label"
                  showLegend
                  series={[
                    { key: 'inflow', name: 'Inflow', color: '#1f9d55', type: 'area', dots: true },
                    { key: 'outflow', name: 'Outflow', color: '#e5484d', type: 'area', dots: true },
                  ]}
                  yFormatter={formatINRShort}
                  tooltipFormatter={(v) => formatINR(v)}
                  height={250}
                  emptyTitle="No cash movements yet"
                  emptyMessage="Money in and out appears once transactions are recorded."
                />
              )}
            </Card>
          </div>

          <div className="dash-row">
            <Card title="Budget vs Actual" subtitle={data?.budget?.period_label}>
              {loading ? (
                <div className="skeleton skeleton--list" aria-label="Loading" />
              ) : (
                <BudgetCard budget={data?.budget} onSetBudget={canManage ? () => setModal('budget') : undefined} />
              )}
            </Card>
            <Card title="Pending Payments">
              {loading ? <div className="skeleton skeleton--list" aria-label="Loading" /> : <PendingPayments items={data?.pending_payments} />}
            </Card>
          </div>

          <div className="dash-row">
            <InsightPanel
              title="Financial Insights"
              items={loading ? undefined : list(insights.items).filter((s) => typeof s === 'string' && s.trim())}
              emptyText={loading ? 'Loading insights…' : undefined}
            />
            <ActionsPanel items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
            {actions.length > 0 && (
              <Card title="Quick Actions">
                <QuickActions actions={actions} columns={2} />
              </Card>
            )}
          </div>
        </>
      )}

      <TransactionModal type={txType} options={options} onClose={() => setTxType(null)} onSave={saveTransaction} />
      <BudgetModal open={modal === 'budget'} budget={data?.budget} onClose={() => setModal(null)} onSave={saveBudget} />
      {/* The ledger hides while a transaction's details are open, so only one dialog is active */}
      <LedgerModal
        open={modal === 'ledger' && !viewing}
        statuses={options.data?.statuses}
        refreshKey={refreshKey}
        onClose={() => setModal(null)}
        onView={setViewing}
      />
      <TransactionDetailsModal transaction={viewing} onClose={() => setViewing(null)} />
    </div>
  )
}
