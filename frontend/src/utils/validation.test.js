import { describe, expect, it } from 'vitest'
import { isEmail, isGstin, isPhone, isUrl, validateFields, validateLogin, validateNewPassword } from './validation'

describe('validateLogin', () => {
  it('requires both fields', () => {
    expect(validateLogin({ username: '  ', password: '' })).toEqual({
      username: 'Please enter your email or username',
      password: 'Please enter your password',
    })
  })
  it('checks the email format only when the username looks like an email', () => {
    expect(validateLogin({ username: 'someone@', password: 'x' }).username).toMatch(/valid email/)
    expect(validateLogin({ username: 'ravi', password: 'x' })).toEqual({})
    expect(validateLogin({ username: 'ravi@hipa.in', password: 'x' })).toEqual({})
  })
  it('leaves password strength rules to the backend', () => {
    expect(validateLogin({ username: 'ravi', password: '1' })).toEqual({})
  })
})

describe('validateNewPassword', () => {
  it('needs 8+ characters with a letter and a number, and a matching confirmation', () => {
    expect(validateNewPassword({ password: 'abc1', confirm: 'abc1' }).password).toMatch(/8 characters/)
    expect(validateNewPassword({ password: 'abcdefgh', confirm: 'abcdefgh' }).password).toMatch(/letter and one number/)
    expect(validateNewPassword({ password: 'abcdefg1', confirm: 'abcdefg2' }).confirm).toMatch(/do not match/)
    expect(validateNewPassword({ password: 'abcdefg1', confirm: 'abcdefg1' })).toEqual({})
  })
})

describe('field validators', () => {
  it('recognises emails, Indian mobile numbers, GSTINs and web addresses', () => {
    expect(isEmail('a@b.in')).toBe(true)
    expect(isEmail('a@b')).toBe(false)
    expect(isPhone('98765 43210')).toBe(true)
    expect(isPhone('+91 98765-43210')).toBe(true)
    expect(isPhone('12345')).toBe(false)
    expect(isGstin('33abcde1234f1z5')).toBe(true)
    expect(isGstin('12345')).toBe(false)
    expect(isUrl('https://hipamasala.com')).toBe(true)
    expect(isUrl('hipamasala')).toBe(false)
  })
})

describe('validateFields (used by every form)', () => {
  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'email', label: 'Email', type: 'email' },
    { name: 'qty', label: 'Quantity', type: 'number', min: 0.01 },
    { name: 'start', label: 'Start' },
    { name: 'end', label: 'End', validate: (v, all) => (v < all.start ? 'End is before start' : undefined) },
  ]
  it('reports required, format, minimum and cross-field problems', () => {
    expect(validateFields(fields, { name: ' ', email: 'x', qty: '0', start: '2026-10-10', end: '2026-10-01' })).toEqual({
      name: 'Name is required',
      email: 'Enter a valid email address',
      qty: 'Must be at least 0.01',
      end: 'End is before start',
    })
  })
  it('skips optional empty fields, including their custom checks', () => {
    expect(validateFields(fields, { name: 'Ravi', email: '', qty: '', start: '', end: '' })).toEqual({})
  })
})
