import { Plus, Trash2 } from 'lucide-react'
import Button from '../../../components/common/Button'
import Input from '../../../components/common/Input'
import { EMPTY_ROW } from '../readings'

/** "Parameters tested": one Parameter + Value row per reading, with Remove and + Add Parameter. */
export default function ParameterRows({ value, onChange, error }) {
  const rows = value?.length ? value : [EMPTY_ROW]
  const update = (i, field, v) => onChange(rows.map((r, j) => (j === i ? { ...r, [field]: v } : r)))

  return (
    <fieldset className="parameter-rows">
      <legend className="field__label">Parameters tested *</legend>
      {rows.map((r, i) => (
        <div className="parameter-rows__row" key={i}>
          <Input aria-label={`Parameter ${i + 1}`} placeholder="Parameter, e.g. Moisture" maxLength={120} value={r.parameter}
                 onChange={(e) => update(i, 'parameter', e.target.value)} />
          <Input aria-label={`Value ${i + 1}`} placeholder="Value, e.g. 8.5" inputMode="decimal" value={r.value}
                 onChange={(e) => update(i, 'value', e.target.value)} />
          <Button variant="ghost" size="sm" icon={Trash2} className="btn--tone-red" aria-label={`Remove parameter ${i + 1}`}
                  disabled={rows.length === 1} onClick={() => onChange(rows.filter((_, j) => j !== i))} />
        </div>
      ))}
      {error && <p className="field__error" role="alert">{error}</p>}
      <div>
        <Button variant="outline" size="sm" icon={Plus} onClick={() => onChange([...rows, { ...EMPTY_ROW }])}>Add Parameter</Button>
      </div>
    </fieldset>
  )
}
