import { RotateCcw, Save } from 'lucide-react'
import { useState } from 'react'
import Button from '../../../components/common/Button'
import Card from '../../../components/common/Card'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Input, { Select, Textarea } from '../../../components/common/Input'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { validateFields } from '../../../utils/validation'

const toText = (v) => (v === null || v === undefined ? '' : String(v))

/**
 * A settings card that loads its values from the API, lets the user edit them in place,
 * and saves with `save(values)`. Save is enabled only when something changed.
 * fields: FormModal-style config ({ name, label, type, options, required, validate, full, placeholder }).
 */
export default function SettingsForm({ title, subtitle, fields, load, save, successMessage = 'Settings saved' }) {
  const toast = useToast()
  const source = useApi(load, [])
  const [draft, setDraft] = useState(null) // null = showing the saved values
  const [errors, setErrors] = useState({})
  const [saveError, setSaveError] = useState('')
  const [pending, setPending] = useState(false)

  const saved = Object.fromEntries(fields.map((f) => [f.name, toText(source.data?.[f.name])]))
  const values = draft ?? saved
  const dirty = draft !== null && fields.some((f) => draft[f.name] !== saved[f.name])

  const set = (name) => (e) => {
    const v = e.target.value
    setDraft((d) => ({ ...(d ?? saved), [name]: v }))
    setErrors((er) => ({ ...er, [name]: undefined }))
  }

  const reset = () => {
    setDraft(null)
    setErrors({})
    setSaveError('')
  }

  const submit = async (e) => {
    e.preventDefault()
    const errs = validateFields(fields, values)
    setErrors(errs)
    if (Object.keys(errs).length) return
    setPending(true)
    setSaveError('')
    try {
      const body = Object.fromEntries(fields.map((f) => [f.name, typeof values[f.name] === 'string' ? values[f.name].trim() : values[f.name]]))
      const result = await save(body)
      source.setData(result && typeof result === 'object' ? result : { ...source.data, ...body })
      setDraft(null)
      toast.success(successMessage)
    } catch (err) {
      const fieldErrs = {}
      for (const f of fields) {
        const v = err.fields?.[f.name]
        const m = Array.isArray(v) ? v[0] : typeof v === 'string' ? v : undefined
        if (m) fieldErrs[f.name] = m
      }
      setErrors(fieldErrs)
      setSaveError(Object.values(fieldErrs).includes(err.message) ? '' : err.message)
    } finally {
      setPending(false)
    }
  }

  return (
    <Card title={title} subtitle={subtitle}>
      {source.loading && !source.data ? (
        <div className="skeleton skeleton--list" aria-label="Loading" />
      ) : source.error && !source.data ? (
        <ErrorMessage message={source.error.message} onRetry={source.reload} />
      ) : (
        <form className="form-grid" onSubmit={submit} noValidate aria-busy={pending || undefined}>
          {saveError && <ErrorMessage message={saveError} className="form-grid__full" />}
          {fields.map((f) => {
            const common = {
              label: f.required ? `${f.label} *` : f.label,
              value: values[f.name],
              onChange: set(f.name),
              error: errors[f.name],
              placeholder: f.placeholder,
              disabled: pending,
              className: f.full || f.type === 'textarea' ? 'form-grid__full' : '',
            }
            if (f.type === 'select') return <Select key={f.name} {...common} options={f.options ?? []} placeholder={f.placeholder ?? 'Select…'} />
            if (f.type === 'textarea') return <Textarea key={f.name} {...common} rows={3} />
            return <Input key={f.name} {...common} type={f.type ?? 'text'} autoComplete={f.autoComplete} />
          })}
          <div className="form-grid__end settings-form__actions">
            <Button type="button" variant="ghost" icon={RotateCcw} onClick={reset} disabled={!dirty || pending}>
              Reset
            </Button>
            <Button type="submit" icon={Save} loading={pending} disabled={!dirty}>
              Save Changes
            </Button>
          </div>
        </form>
      )}
    </Card>
  )
}
