import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import ConfirmDialog from './ConfirmDialog'

function setup(onConfirm) {
  const onClose = vi.fn()
  render(
    <ConfirmDialog open onClose={onClose} onConfirm={onConfirm} danger title="Cancel this order?" message="This cannot be undone." confirmLabel="Cancel Order" cancelLabel="Keep Order" />,
  )
  return { onClose, user: userEvent.setup() }
}

describe('ConfirmDialog', () => {
  it('runs the action and closes when confirmed', async () => {
    const onConfirm = vi.fn().mockResolvedValue()
    const { onClose, user } = setup(onConfirm)
    expect(screen.getByRole('dialog', { name: 'Cancel this order?' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel Order' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    expect(onClose).toHaveBeenCalled()
  })

  it('stays open and shows the reason when the action fails', async () => {
    const { onClose, user } = setup(vi.fn().mockRejectedValue(new Error('Order already dispatched')))
    await user.click(screen.getByRole('button', { name: 'Cancel Order' }))
    expect(await screen.findByText('Order already dispatched')).toBeInTheDocument()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('does nothing when cancelled', async () => {
    const onConfirm = vi.fn()
    const { onClose, user } = setup(onConfirm)
    await user.click(screen.getByRole('button', { name: 'Keep Order' }))
    expect(onConfirm).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalled()
  })
})
