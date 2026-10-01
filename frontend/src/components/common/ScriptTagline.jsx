/** Handwritten-style slogan used in the top bar and login panel (a slogan, not the logo). */
export default function ScriptTagline({ className = '' }) {
  return (
    <div className={`script-tagline ${className}`}>
      <span>Spices for a</span>
      <span className="script-tagline__2">Better Tomorrow</span>
      <svg viewBox="0 0 28 28" width="26" height="26" aria-hidden>
        <path d="M4 24C4 12 12 4 26 3c-1 14-9 22-22 21z" fill="#2e8b47" />
        <path d="M5 23 18 10" stroke="#e9f6ec" strokeWidth="1.3" />
      </svg>
    </div>
  )
}
