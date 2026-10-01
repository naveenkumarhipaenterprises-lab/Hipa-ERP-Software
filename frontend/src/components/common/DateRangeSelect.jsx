import { CalendarDays, ChevronDown } from 'lucide-react'
import { DATE_RANGES } from '../../utils/constants'

export default function DateRangeSelect({ value, onChange, options = DATE_RANGES }) {
  return (
    <label className="pill-select">
      <CalendarDays size={18} aria-hidden />
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Date range">
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown size={16} aria-hidden />
    </label>
  )
}

/** Small borderless dropdown used in card headers ("Monthly", "Last 30 Days"). */
export function MiniSelect({ value, onChange, options, label }) {
  return (
    <label className="mini-select">
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        {options.map((o) => {
          const opt = typeof o === 'string' ? { value: o, label: o } : o
          return (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          )
        })}
      </select>
      <ChevronDown size={14} aria-hidden />
    </label>
  )
}
