import { ChevronDown } from 'lucide-react'
import { useId } from 'react'

function Field({ id, label, error, hint, children, className = '' }) {
  return (
    <div className={`field ${error ? 'field--error' : ''} ${className}`}>
      {label && (
        <label className="field__label" htmlFor={id}>
          {label}
        </label>
      )}
      {children}
      {error ? (
        <p className="field__error" id={`${id}-error`} role="alert">
          {error}
        </p>
      ) : (
        hint && (
          <p className="field__hint" id={`${id}-hint`}>
            {hint}
          </p>
        )
      )}
    </div>
  )
}

/** Joins the field's own error/hint ids with any aria-describedby passed in. */
function describedBy(inputId, error, hint, extra) {
  const ids = [error ? `${inputId}-error` : hint ? `${inputId}-hint` : null, extra].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
}

export default function Input({ label, error, hint, icon: Icon, right, className, id, 'aria-describedby': extraDesc, ...rest }) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <Field id={inputId} label={label} error={error} hint={hint} className={className}>
      <div className={`control ${Icon ? 'control--icon' : ''} ${right ? 'control--right' : ''}`}>
        {Icon && <Icon size={18} className="control__icon" aria-hidden />}
        <input
          id={inputId}
          className="control__input"
          aria-invalid={Boolean(error)}
          aria-describedby={describedBy(inputId, error, hint, extraDesc)}
          {...rest}
        />
        {right && <div className="control__right">{right}</div>}
      </div>
    </Field>
  )
}

/** options: array of strings or { value, label } */
export function Select({ label, error, hint, options = [], className, id, placeholder, ...rest }) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <Field id={selectId} label={label} error={error} hint={hint} className={className}>
      <div className="control control--select">
        <select id={selectId} className="control__input" aria-invalid={Boolean(error)} {...rest}>
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((o) => {
            const opt = typeof o === 'string' ? { value: o, label: o } : o
            return (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            )
          })}
        </select>
        <ChevronDown size={16} className="control__chevron" aria-hidden />
      </div>
    </Field>
  )
}

export function Textarea({ label, error, hint, className, id, ...rest }) {
  const autoId = useId()
  const areaId = id ?? autoId
  return (
    <Field id={areaId} label={label} error={error} hint={hint} className={className}>
      <div className="control">
        <textarea id={areaId} className="control__input control__input--area" aria-invalid={Boolean(error)} {...rest} />
      </div>
    </Field>
  )
}

export function Toggle({ checked, onChange, label, disabled, id }) {
  const autoId = useId()
  const toggleId = id ?? autoId
  return (
    <label className="toggle" htmlFor={toggleId}>
      <input
        id={toggleId}
        type="checkbox"
        role="switch"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="toggle__track" aria-hidden>
        <span className="toggle__thumb" />
      </span>
      {label && <span className="toggle__label">{label}</span>}
    </label>
  )
}

export function Checkbox({ checked, onChange, label, id }) {
  const autoId = useId()
  const boxId = id ?? autoId
  return (
    <label className="checkbox" htmlFor={boxId}>
      <input id={boxId} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}
