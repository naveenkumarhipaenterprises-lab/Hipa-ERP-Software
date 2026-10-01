import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import Table from './Table'

const columns = [
  { key: 'name', header: 'Name' },
  { key: 'amount', header: 'Amount', align: 'right' },
  { key: 'act', header: 'Actions', sticky: true, render: () => <button type="button">Edit</button> },
]
const rows = Array.from({ length: 12 }, (_, i) => ({ id: i + 1, name: `Row ${i + 1}`, amount: i }))

describe('Table', () => {
  it('shows the empty message instead of rows when there is no data', () => {
    render(<Table columns={columns} data={[]} emptyTitle="No orders yet" emptyMessage="Orders will appear here." />)
    expect(screen.getByText('No orders yet')).toBeInTheDocument()
    expect(screen.getByText('Orders will appear here.')).toBeInTheDocument()
  })

  it('shows loading placeholders and hides the empty message while loading', () => {
    const { container } = render(<Table columns={columns} data={[]} loading />)
    expect(container.querySelectorAll('.table__skeleton-row')).toHaveLength(5)
    expect(screen.queryByText('No records available')).not.toBeInTheDocument()
  })

  it('pages through data locally', async () => {
    const user = userEvent.setup()
    render(<Table columns={columns} data={rows} pageSize={10} />)
    expect(screen.getByText('Showing 1–10 of 12')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(screen.getByText('Showing 11–12 of 12')).toBeInTheDocument()
    expect(screen.getByText('Row 12')).toBeInTheDocument()
    expect(screen.queryByText('Row 1')).not.toBeInTheDocument()
  })

  it('asks the server for another page in server-side mode', async () => {
    const user = userEvent.setup()
    const onPageChange = vi.fn()
    render(<Table columns={columns} data={rows.slice(0, 10)} pagination={{ page: 1, pageSize: 10, total: 23, onPageChange }} />)
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
  })

  it('keeps rows that share a name apart (no id: falls back to position, never the name)', () => {
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
    const same = [
      { name: 'Sri Lakshmi Traders', amount: 1 },
      { name: 'Sri Lakshmi Traders', amount: 2 },
    ]
    render(<Table columns={columns.slice(0, 2)} data={same} />)
    expect(screen.getAllByText('Sri Lakshmi Traders')).toHaveLength(2)
    expect(errors).not.toHaveBeenCalled()
  })

  it('passes the row position to a rowKey function', () => {
    const rowKey = vi.fn((r, i) => r.id ?? i)
    render(<Table columns={columns.slice(0, 1)} data={[{ name: 'A' }, { name: 'B' }]} rowKey={rowKey} />)
    expect(rowKey).toHaveBeenCalledWith({ name: 'A' }, 0)
    expect(rowKey).toHaveBeenCalledWith({ name: 'B' }, 1)
  })

  it('pins sticky action columns to the right edge', () => {
    render(<Table columns={columns} data={rows.slice(0, 1)} />)
    const header = screen.getByRole('columnheader', { name: 'Actions' })
    expect(header).toHaveClass('table__sticky')
    const row = screen.getAllByRole('row')[1]
    expect(within(row).getByRole('button', { name: 'Edit' }).closest('td')).toHaveClass('table__sticky')
  })
})
