import { ChevronDown, Globe } from 'lucide-react'
import { useState } from 'react'
import { LANGUAGES } from '../../utils/constants'

const KEY = 'hipa_lang'
const isAvailable = (value) => LANGUAGES.some((l) => l.value === value)

function readLang() {
  try {
    const saved = localStorage.getItem(KEY)
    return isAvailable(saved) ? saved : 'en'
  } catch {
    return 'en'
  }
}

/** Language picker on the login pages; it lists only the languages in LANGUAGES (English). */
export default function LanguageSelector() {
  const [lang, setLang] = useState(readLang)

  const change = (value) => {
    if (!isAvailable(value)) return
    setLang(value)
    try {
      localStorage.setItem(KEY, value)
    } catch {
      /* storage unavailable: keep in memory only */
    }
    document.documentElement.lang = value
  }

  return (
    <label className="lang-select">
      <Globe size={18} aria-hidden />
      <select value={lang} onChange={(e) => change(e.target.value)} aria-label="Language">
        {LANGUAGES.map((l) => (
          <option key={l.value} value={l.value}>
            {l.label}
          </option>
        ))}
      </select>
      <ChevronDown size={16} aria-hidden />
    </label>
  )
}
