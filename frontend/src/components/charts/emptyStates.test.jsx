import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ActionsPanel, InsightPanel } from '../dashboard/InsightPanel'
import DonutChart from './DonutChart'
import ProgressList from './ProgressList'
import SeriesChart from './SeriesChart'
import Sparkline from './Sparkline'

// The rule for this project: with no real data, show an empty state, never invented values
describe('empty states instead of invented data', () => {
  it('SeriesChart shows its empty message when nothing can be plotted', () => {
    render(<SeriesChart data={[]} xKey="label" series={[{ key: 'sales', name: 'Sales' }]} emptyTitle="No sales recorded" />)
    expect(screen.getByText('No sales recorded')).toBeInTheDocument()
  })

  it('DonutChart shows its empty message when every value is zero', () => {
    render(<DonutChart data={[{ name: 'A', value: 0 }]} emptyTitle="No product sales" />)
    expect(screen.getByText('No product sales')).toBeInTheDocument()
  })

  it('ProgressList shows its empty message with no items', () => {
    render(<ProgressList items={[]} emptyTitle="No orders in this period" />)
    expect(screen.getByText('No orders in this period')).toBeInTheDocument()
  })

  it('Sparkline shows a dash when there are fewer than two points', () => {
    render(<Sparkline values={[5]} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('insight panels say insights are not available rather than making them up', () => {
    render(
      <>
        <InsightPanel title="AI Sales Insight" items={[]} />
        <ActionsPanel items={[]} />
      </>,
    )
    expect(screen.getByText(/No insights available yet/)).toBeInTheDocument()
    expect(screen.getByText('No recommended actions right now.')).toBeInTheDocument()
  })

  it('lists with repeated labels or sentences render every entry without React key warnings', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <>
        <ProgressList items={[{ name: 'Chennai', value: 5 }, { name: 'Chennai', value: 3 }]} />
        <InsightPanel title="AI Insight" items={['Same insight', 'Same insight']} />
      </>,
    )
    expect(screen.getAllByText('Chennai')).toHaveLength(2)
    expect(screen.getAllByText('Same insight')).toHaveLength(2)
    expect(errors).not.toHaveBeenCalled()
  })

  it('insight panels show what the API sends', () => {
    render(<InsightPanel title="AI Sales Insight" items={['Chilli sales rose 12%']} />)
    expect(screen.getByText('Chilli sales rose 12%')).toBeInTheDocument()
  })
})
