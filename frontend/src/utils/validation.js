const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const PHONE_RE = /^[6-9]\d{9}$/

export const isEmail = (v) => EMAIL_RE.test(String(v).trim())
export const isPhone = (v) => PHONE_RE.test(String(v).replace(/[\s-]/g, '').replace(/^\+?91/, ''))

// 15 characters: state code, PAN, entity number, 'Z', checksum (format check only)
const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/
export const isGstin = (v) => GSTIN_RE.test(String(v).trim().toUpperCase())

const URL_RE = /^https?:\/\/[^\s.]+\.[^\s]+$/i
export const isUrl = (v) => URL_RE.test(String(v).trim())

/** Login only checks that both fields are filled; password rules are the backend's job. */
export function validateLogin({ username, password }) {
  const errors = {}
  if (!username?.trim()) errors.username = 'Please enter your email or username'
  else if (username.includes('@') && !isEmail(username)) errors.username = 'Enter a valid email address or a username'
  if (!password) errors.password = 'Please enter your password'
  return errors
}

export function validateNewPassword({ password, confirm }) {
  const errors = {}
  if (!password || password.length < 8) errors.password = 'Use at least 8 characters'
  else if (!/[A-Za-z]/.test(password) || !/\d/.test(password))
    errors.password = 'Include at least one letter and one number'
  if (confirm !== password) errors.confirm = 'Passwords do not match'
  return errors
}

/**
 * Validates values against a field config used by FormModal:
 * { name, label, required, type: 'email' | 'tel' | 'number', min, validate?(value, values) -> message }
 * `validate` handles checks that involve other fields (e.g. due date after start date).
 */
export function validateFields(fields, values) {
  const errors = {}
  for (const f of fields) {
    const v = values[f.name]
    const empty = v === undefined || v === null || String(v).trim() === ''
    if (f.required && empty) {
      errors[f.name] = `${f.label} is required`
      continue
    }
    if (empty) continue
    if (f.type === 'email' && !isEmail(v)) errors[f.name] = 'Enter a valid email address'
    if (f.type === 'tel' && !isPhone(v)) errors[f.name] = 'Enter a valid 10-digit mobile number'
    if (f.type === 'number') {
      const n = Number(v)
      if (Number.isNaN(n)) errors[f.name] = 'Enter a number'
      else if (f.min !== undefined && n < f.min) errors[f.name] = `Must be at least ${f.min}`
    }
    if (!errors[f.name] && f.validate) {
      const message = f.validate(v, values)
      if (message) errors[f.name] = message
    }
  }
  return errors
}
