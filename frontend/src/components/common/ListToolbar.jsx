import { Search } from 'lucide-react'
import Input, { Select } from './Input'

/**
 * Search box + select filters + optional date range above server-paginated lists (see hooks/usePagedList).
 * filters: [{ name, label, value, options }] ; dates: { from, to, onChange(name, value) } | undefined
 */
export default function ListToolbar({ search, onSearch, searchLabel, filters = [], onFilter, dates }) {
  return (
    <div className="toolbar">
      <label className="toolbar__search">
        <Search size={16} aria-hidden />
        <input type="search" value={search} onChange={(e) => onSearch(e.target.value)} placeholder={searchLabel} aria-label={searchLabel} />
      </label>
      {filters.map((f) => (
        <Select
          key={f.name}
          className="field--inline"
          aria-label={f.label}
          value={f.value}
          onChange={(e) => onFilter(f.name, e.target.value)}
          options={f.options}
        />
      ))}
      {dates && (
        <>
          <Input className="field--inline" type="date" aria-label="From date" value={dates.from} onChange={(e) => dates.onChange('date_from', e.target.value)} />
          <Input className="field--inline" type="date" aria-label="To date" value={dates.to} onChange={(e) => dates.onChange('date_to', e.target.value)} />
        </>
      )}
    </div>
  )
}
