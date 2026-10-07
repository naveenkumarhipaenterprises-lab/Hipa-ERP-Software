import { CalendarDays, Megaphone, MousePointer2, Plus, ShoppingCart, Sparkles, SquarePen, Users, UsersRound } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { marketingApi } from '../../api/marketingApi'
import DonutChart from '../../components/charts/DonutChart'
import ProgressList from '../../components/charts/ProgressList'
import SeriesChart from '../../components/charts/SeriesChart'
import Button from '../../components/common/Button'
import Card from '../../components/common/Card'
import DateRangeSelect, { MiniSelect } from '../../components/common/DateRangeSelect'
import ErrorMessage from '../../components/common/ErrorMessage'
import PageHeader from '../../components/common/PageHeader'
import { ActionsPanel, InsightPanel } from '../../components/dashboard/InsightPanel'
import QuickActions from '../../components/dashboard/QuickActions'
import StatCard from '../../components/dashboard/StatCard'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { CHART_COLORS, DATE_RANGES } from '../../utils/constants'
import { formatCompact, formatINR, formatNumber, formatPercent } from '../../utils/formatters'
import CampaignFormModal from './components/CampaignFormModal'
import CampaignsTable from './components/CampaignsTable'
import ContentCalendarModal from './components/ContentCalendarModal'
import SchedulePostModal from './components/SchedulePostModal'
import TopContent from './components/TopContent'

// Roles that may create campaigns and schedule posts (the backend enforces the same rule)
const MARKETING_MANAGERS = ['admin', 'management', 'marketing']

const PERFORMANCE_DAYS = [
  { value: '30', label: 'Last 30 Days' },
  { value: '14', label: 'Last 14 Days' },
  { value: '7', label: 'Last 7 Days' },
]

const KPIS = [
  { key: 'reach', label: 'Total Reach', icon: Users, tone: 'green', format: formatNumber },
  { key: 'engagement', label: 'Engagement', icon: UsersRound, tone: 'blue', format: formatNumber },
  { key: 'website_visitors', label: 'Website Visitors', icon: MousePointer2, tone: 'red', format: formatNumber },
  { key: 'marketing_sales', label: 'Sales from Marketing', icon: ShoppingCart, tone: 'yellow', format: formatINR },
]

const list = (v) => (Array.isArray(v) ? v : [])
const has = (v) => v !== null && v !== undefined && v !== ''

export default function MarketingPage() {
  const { user, can } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [days, setDays] = useState(PERFORMANCE_DAYS[0].value)
  const [platform, setPlatform] = useState('')
  const [modal, setModal] = useState(null) // 'post' | 'calendar'
  const [refreshKey, setRefreshKey] = useState(0)

  const canManage = MARKETING_MANAGERS.includes(user?.role)
  // ?new=campaign (from the dashboard's Quick Actions) opens the campaign form
  const creatingCampaign = canManage && params.get('new') === 'campaign'

  const overview = useApi(() => marketingApi.getOverview({ range }), [range, refreshKey])
  const performance = useApi(() => marketingApi.getPerformance({ days }), [days, refreshKey])
  const audience = useApi(() => marketingApi.getAudience({ platform }), [platform, refreshKey])
  const options = useApi(() => marketingApi.getOptions(), [])

  // Never show figures from another range or a failed request
  const loading = overview.loading
  const failed = Boolean(overview.error) && !loading
  const data = !loading && !failed ? (overview.data ?? {}) : null
  const insights = data?.insights ?? {}
  const platforms = list(options.data?.platforms)

  const audienceRows = list(audience.data).map((a) => ({ name: a.name, value: Number(a.value) || 0 }))
  const audienceTotal = audienceRows.reduce((s, a) => s + a.value, 0)

  const refresh = () => setRefreshKey((k) => k + 1)
  const setCampaignParam = (on) =>
    setParams(
      (p) => {
        const next = new URLSearchParams(p)
        if (on) next.set('new', 'campaign')
        else next.delete('new')
        return next
      },
      { replace: true },
    )

  const createCampaign = async (values) => {
    const created = await marketingApi.createCampaign(values)
    toast.success(`Campaign "${created?.name ?? values.name}" created`)
    refresh()
  }

  const schedulePost = async (values) => {
    await marketingApi.schedulePost(values)
    toast.success('Post added to the content calendar')
    refresh()
  }

  const tools = [
    ...(canManage
      ? [
          { label: 'Create Post', icon: SquarePen, tone: 'red', onClick: () => setModal('post') },
          { label: 'Ad Campaign', icon: Megaphone, tone: 'blue', onClick: () => setCampaignParam(true) },
        ]
      : []),
    { label: 'Content Calendar', icon: CalendarDays, tone: 'green', onClick: () => setModal('calendar') },
    ...(can('aiAssistant')
      ? [{ label: 'Generate with AI', icon: Sparkles, tone: 'purple', onClick: () => navigate('/ai-assistant?q=Suggest%20a%20marketing%20campaign%20idea') }]
      : []),
  ]

  const skeleton = <div className="skeleton skeleton--chart-inner" aria-label="Loading" />

  return (
    <div className="page">
      <title>Marketing | HIPA MASALA</title>
      <PageHeader icon={Megaphone} title="Marketing" subtitle="Grow your brand with data-driven marketing insights">
        <DateRangeSelect value={range} onChange={setRange} />
        {canManage && (
          <Button icon={Plus} onClick={() => setCampaignParam(true)}>
            Create Campaign
          </Button>
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
                />
              )
            })}
          </div>

          <div className="dash-row">
            <Card
              title="Marketing Performance"
              className="dash-row__wide"
              action={<MiniSelect label="Performance period" value={days} onChange={setDays} options={PERFORMANCE_DAYS} />}
            >
              {performance.loading ? (
                skeleton
              ) : performance.error ? (
                <ErrorMessage message={performance.error.message} onRetry={performance.reload} />
              ) : (
                <SeriesChart
                  data={list(performance.data)}
                  xKey="label"
                  showLegend
                  series={[
                    { key: 'reach', name: 'Reach', color: CHART_COLORS[1], type: 'area', dots: true },
                    { key: 'engagement', name: 'Engagement', color: CHART_COLORS[0], type: 'area', dots: true },
                    { key: 'website_visitors', name: 'Website Visitors', color: CHART_COLORS[2], type: 'area', dots: true },
                  ]}
                  yFormatter={formatCompact}
                  tooltipFormatter={(v) => formatNumber(v)}
                  height={260}
                  emptyTitle="No performance data yet"
                  emptyMessage="Reach, engagement and visitors appear once platforms report data."
                />
              )}
            </Card>
            <Card title="Channel Performance" subtitle="Share of engagement">
              {loading ? (
                skeleton
              ) : (
                <ProgressList
                  items={list(data?.channels).map((c, i) => ({ name: c.name, value: Number(c.value) || 0, color: CHART_COLORS[i % CHART_COLORS.length] }))}
                  format={(v) => formatPercent(v, 0)}
                  emptyTitle="No channel data yet"
                  emptyMessage="Engagement by channel will appear here."
                />
              )}
            </Card>
            <Card title="Top Performing Content">{loading ? skeleton : <TopContent items={data?.top_content} />}</Card>
          </div>

          <CampaignsTable
            refreshKey={refreshKey}
            statuses={options.data?.statuses}
            platforms={platforms}
            canManage={canManage}
            onChanged={refresh}
          />

          <div className="dash-row">
            <Card
              title="Audience Insights"
              action={
                platforms.length > 0 && (
                  <MiniSelect
                    label="Audience platform"
                    value={platform}
                    onChange={setPlatform}
                    options={[{ value: '', label: 'All Platforms' }, ...platforms]}
                  />
                )
              }
            >
              {audience.loading ? (
                skeleton
              ) : audience.error ? (
                <ErrorMessage message={audience.error.message} onRetry={audience.reload} />
              ) : (
                <DonutChart
                  data={audienceRows}
                  valueFormatter={(v) => formatNumber(v)}
                  legendValue={(d) => (audienceTotal ? formatPercent((d.value / audienceTotal) * 100, 1) : '—')}
                  centerValue={formatCompact(audienceTotal)}
                  centerLabel="Audience"
                  size={170}
                  emptyTitle="No audience data yet"
                  emptyMessage="The audience split appears once platforms report it."
                />
              )}
            </Card>
            <div className="stack">
              <InsightPanel
                title="AI Marketing Insight"
                text={loading ? undefined : insights.text}
                emptyText={loading ? 'Loading insights…' : undefined}
              />
              <ActionsPanel items={loading ? undefined : list(insights.actions)} emptyText={loading ? 'Loading…' : undefined} />
            </div>
            <Card title="Quick Tools">
              <QuickActions actions={tools} columns={2} />
            </Card>
          </div>
        </>
      )}

      <CampaignFormModal open={creatingCampaign} options={options} onClose={() => setCampaignParam(false)} onCreate={createCampaign} />
      <SchedulePostModal open={modal === 'post'} options={options} onClose={() => setModal(null)} onSchedule={schedulePost} />
      <ContentCalendarModal
        open={modal === 'calendar'}
        refreshKey={refreshKey}
        onClose={() => setModal(null)}
        onSchedule={canManage ? () => setModal('post') : undefined}
        canManage={canManage}
      />
    </div>
  )
}
