import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { LANGUAGES } from './utils/constants'

// Restore the language chosen on the login screen before first paint
try {
  const saved = localStorage.getItem('hipa_lang')
  document.documentElement.lang = LANGUAGES.some((l) => l.value === saved) ? saved : 'en'
} catch {
  /* storage unavailable: keep the default */
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
