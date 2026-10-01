import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithApp } from '../../test/render'
import LoginForm from './LoginForm'

const setup = (onSubmit = vi.fn()) => ({ onSubmit, ...renderWithApp(<LoginForm onSubmit={onSubmit} />) })

describe('LoginForm', () => {
  it('starts on the username field with "Remember me" off', () => {
    setup()
    expect(screen.getByLabelText('Email / Username')).toHaveFocus()
    expect(screen.getByLabelText('Remember me')).not.toBeChecked()
  })

  it('asks for both fields before sending', async () => {
    const { user, onSubmit } = setup()
    await user.click(screen.getByRole('button', { name: 'Login' }))
    expect(screen.getByText('Please enter your email or username')).toBeInTheDocument()
    expect(screen.getByText('Please enter your password')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('sends a trimmed username', async () => {
    const { user, onSubmit } = setup(vi.fn().mockResolvedValue())
    await user.type(screen.getByLabelText('Email / Username'), '  ravi  ')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByLabelText('Remember me'))
    await user.click(screen.getByRole('button', { name: 'Login' }))
    expect(onSubmit).toHaveBeenCalledWith({ username: 'ravi', password: 'secret', remember: true })
  })

  it('shows the server message and clears the password when login fails', async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error('No active account found with the given credentials')))
    await user.type(screen.getByLabelText('Email / Username'), 'ravi')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Login' }))
    expect(await screen.findByText('No active account found with the given credentials')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('shows a field-level server error under that field only', async () => {
    const err = Object.assign(new Error('This password has expired.'), { fields: { password: ['This password has expired.'] } })
    const { user } = setup(vi.fn().mockRejectedValue(err))
    await user.type(screen.getByLabelText('Email / Username'), 'ravi')
    await user.type(screen.getByLabelText('Password'), 'old')
    await user.click(screen.getByRole('button', { name: 'Login' }))
    expect(await screen.findByText('This password has expired.')).toHaveClass('field__error')
    expect(document.querySelector('.error-message')).toBeNull()
  })
})
