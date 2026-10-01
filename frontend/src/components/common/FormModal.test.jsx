import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import FormModal from './FormModal'

const fields = [
  { name: 'name', label: 'Customer name', required: true },
  { name: 'qty', label: 'Quantity (kg)', type: 'number', required: true, min: 0.01 },
  { name: 'status', label: 'Status', type: 'select', options: [{ value: 'a', label: 'Active' }] },
]

function setup(onSubmit) {
  const onClose = vi.fn()
  const user = userEvent.setup()
  render(<FormModal open onClose={onClose} title="New thing" fields={fields} submitLabel="Save" onSubmit={onSubmit} />)
  return { user, onClose }
}

describe('FormModal', () => {
  it('does not render when closed', () => {
    render(<FormModal open={false} onClose={() => {}} title="Hidden" fields={fields} onSubmit={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('is an accessible dialog with the first field focused', () => {
    setup(vi.fn())
    expect(screen.getByRole('dialog', { name: 'New thing' })).toBeInTheDocument()
    expect(screen.getByLabelText('Customer name *')).toHaveFocus()
  })

  it('validates before sending anything', async () => {
    const onSubmit = vi.fn()
    const { user } = setup(onSubmit)
    await user.type(screen.getByLabelText('Quantity (kg) *'), '0')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(screen.getByText('Customer name is required')).toBeInTheDocument()
    expect(screen.getByText('Must be at least 0.01')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('sends typed values (numbers as numbers) and closes on success', async () => {
    const onSubmit = vi.fn().mockResolvedValue()
    const { user, onClose } = setup(onSubmit)
    await user.type(screen.getByLabelText('Customer name *'), 'Sri Lakshmi Traders')
    await user.type(screen.getByLabelText('Quantity (kg) *'), '12.5')
    await user.selectOptions(screen.getByLabelText('Status'), 'a')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(onSubmit).toHaveBeenCalledWith({ name: 'Sri Lakshmi Traders', qty: 12.5, status: 'a' })
    expect(onClose).toHaveBeenCalled()
  })

  it('shows server field errors under the field and stays open', async () => {
    const err = Object.assign(new Error('Exceeds available stock'), { fields: { qty: ['Exceeds available stock'] } })
    const { user, onClose } = setup(vi.fn().mockRejectedValue(err))
    await user.type(screen.getByLabelText('Customer name *'), 'Ravi')
    await user.type(screen.getByLabelText('Quantity (kg) *'), '99')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Exceeds available stock')).toBeInTheDocument()
    expect(screen.getByLabelText('Quantity (kg) *')).toHaveAttribute('aria-invalid', 'true')
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows other server errors as a banner', async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error('Cannot reach the server.')))
    await user.type(screen.getByLabelText('Customer name *'), 'Ravi')
    await user.type(screen.getByLabelText('Quantity (kg) *'), '5')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Cannot reach the server.')
  })

  it('closes on Escape', async () => {
    const { user, onClose } = setup(vi.fn())
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
