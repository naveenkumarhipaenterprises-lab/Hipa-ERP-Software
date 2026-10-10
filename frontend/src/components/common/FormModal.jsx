import { useState } from 'react'
import { validateFields } from '../../utils/validation'
import Button from './Button'
import ErrorMessage from './ErrorMessage'
import Input, { Select, Textarea } from './Input'
import Modal from './Modal'

/**
 * Config-driven form in a modal.
 * fields: [{ name, label, type?: 'text'|'number'|'email'|'tel'|'date'|'select'|'textarea',
 *            options?, required?, placeholder?, min?, full?, visible?(values) }]
 *   visible: show the field only when it returns true (hidden fields are neither validated nor sent)
 *   render({ value, error, onChange }): a custom full-width field (e.g. rows of inputs); check it with `validate`
 * summary(values): optional live content under the fields (e.g. totals calculated as the user types)
 * onSubmit(values) may return a promise; the modal closes when it resolves.
 */
export default function FormModal({ open, onClose, title, subtitle, fields, initialValues, submitLabel = 'Save', onSubmit, summary }) {
  if (!open) return null
  // Keyed inner form so every open starts from fresh values
  return (
    <FormModalInner
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      fields={fields}
      initialValues={initialValues}
      submitLabel={submitLabel}
      onSubmit={onSubmit}
      summary={summary}
    />
  )
}

function FormModalInner({ onClose, title, subtitle, fields: allFields, initialValues = {}, submitLabel, onSubmit, summary }) {
  const [values, setValues] = useState(() =>
    Object.fromEntries(allFields.map((f) => [f.name, initialValues[f.name] ?? f.defaultValue ?? ''])),
  )
  const fields = allFields.filter((f) => !f.visible || f.visible(values))
  const [errors, setErrors] = useState({})
  const [submitError, setSubmitError] = useState(null)
  const [pending, setPending] = useState(false)

  const set = (name, value) => {
    setValues((v) => ({ ...v, [name]: value }))
    if (errors[name]) setErrors((e) => ({ ...e, [name]: undefined }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validateFields(fields, values)
    setErrors(errs)
    if (Object.keys(errs).length) return
    const cleaned = Object.fromEntries(
      fields.map((f) => [f.name, f.type === 'number' && values[f.name] !== '' ? Number(values[f.name]) : values[f.name]]),
    )
    setPending(true)
    setSubmitError(null)
    try {
      await onSubmit(cleaned)
      onClose()
    } catch (err) {
      // DRF field errors go under their fields; anything else in the banner
      const fieldErrs = {}
      for (const f of fields) {
        const v = err.fields?.[f.name]
        const msg = Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined
        if (msg) fieldErrs[f.name] = msg
      }
      setErrors(fieldErrs)
      const onlyFields = Object.values(fieldErrs).includes(err.message)
      setSubmitError(onlyFields ? null : err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={title}
      subtitle={subtitle}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="form-modal" loading={pending}>
            {submitLabel}
          </Button>
        </>
      }
    >
      <form id="form-modal" className="form-grid" onSubmit={handleSubmit} noValidate>
        {submitError && <ErrorMessage message={submitError} className="form-grid__full" />}
        {fields.map((f) => {
          const common = {
            label: f.required ? `${f.label} *` : f.label,
            value: values[f.name],
            error: errors[f.name],
            placeholder: f.placeholder,
            className: f.full || f.type === 'textarea' ? 'form-grid__full' : '',
          }
          if (f.render)
            return (
              <div key={f.name} className="form-grid__full">
                {f.render({ value: values[f.name], error: errors[f.name], onChange: (v) => set(f.name, v) })}
              </div>
            )
          if (f.type === 'select')
            return (
              <Select
                {...common}
                key={f.name}
                options={f.options}
                placeholder={f.placeholder ?? 'Select…'}
                onChange={(e) => set(f.name, e.target.value)}
              />
            )
          if (f.type === 'textarea')
            return <Textarea {...common} key={f.name} rows={3} onChange={(e) => set(f.name, e.target.value)} />
          return (
            <Input
              {...common}
              key={f.name}
              type={f.type ?? 'text'}
              min={f.min}
              inputMode={f.type === 'number' ? 'decimal' : undefined}
              onChange={(e) => set(f.name, e.target.value)}
            />
          )
        })}
        {summary && <div className="form-grid__full">{summary(values)}</div>}
      </form>
    </Modal>
  )
}
