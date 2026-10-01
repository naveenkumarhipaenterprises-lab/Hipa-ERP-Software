import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import StatCard from './StatCard'

describe('StatCard', () => {
  it('shows a dash and "No data available" instead of a number when the API has no value', () => {
    render(<StatCard label="Total Sales" value={null} change={5} />)
    expect(screen.getByText('—')).toBeInTheDocument()
    expect(screen.getByText('No data available')).toBeInTheDocument()
    // no invented change figure either
    expect(screen.queryByText('5%')).not.toBeInTheDocument()
  })

  it('shows the value and the change from the API', () => {
    render(<StatCard label="Total Sales" value="₹12,34,567" change={4.2} changeLabel="vs prev. period" />)
    expect(screen.getByText('₹12,34,567')).toBeInTheDocument()
    expect(screen.getByText('4.2%')).toHaveClass('text-up')
  })

  it('colours a fall as good for costs', () => {
    render(<StatCard label="Expenses" value="₹5" change={-3} goodWhenDown />)
    expect(screen.getByText('3%')).toHaveClass('text-up')
  })

  it('shows a loading placeholder while loading', () => {
    render(<StatCard label="Total Sales" loading />)
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
    expect(screen.queryByText('No data available')).not.toBeInTheDocument()
  })
})
