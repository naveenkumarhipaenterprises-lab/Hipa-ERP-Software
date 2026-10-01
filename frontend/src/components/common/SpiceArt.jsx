/** Illustrated bowls of spice powder, chillies and leaves (pure SVG, no image assets). */
const BOWLS = [
  { cx: 70, cy: 118, r: 44, powder: '#e8a317', shade: '#b97d0c' },
  { cx: 150, cy: 132, r: 40, powder: '#c0392b', shade: '#8e2418' },
  { cx: 118, cy: 72, r: 34, powder: '#8d6e4c', shade: '#634a31' },
  { cx: 196, cy: 84, r: 30, powder: '#a08a4e', shade: '#6f5f33' },
]

export default function SpiceArt({ className = '', width = 240 }) {
  return (
    <svg className={className} width={width} viewBox="0 0 240 180" aria-hidden>
      <defs>
        {BOWLS.map((b, i) => (
          <radialGradient key={i} id={`powder-${i}`} cx="45%" cy="35%" r="70%">
            <stop offset="0%" stopColor={b.powder} stopOpacity="1" />
            <stop offset="100%" stopColor={b.shade} />
          </radialGradient>
        ))}
        <linearGradient id="bowl-wood" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#8a5a33" />
          <stop offset="100%" stopColor="#4a2d17" />
        </linearGradient>
      </defs>

      {/* leaves */}
      <path d="M20 60c10-24 34-30 52-24-8 22-30 32-52 24z" fill="#3f8f3a" />
      <path d="M200 30c18-12 34-8 40 2-16 14-32 12-40-2z" fill="#4c9a44" />
      <path d="M8 150c4-22 22-32 40-30-4 20-20 32-40 30z" fill="#357a31" />

      {/* chillies */}
      <path d="M150 30c24-6 50 4 62 26-2 4-8 4-12 0-12-14-30-20-50-18z" fill="#c62828" />
      <path d="M148 30c-4-6-2-12 4-14" stroke="#2e7d32" strokeWidth="4" fill="none" strokeLinecap="round" />
      <path d="M170 168c22 4 44-4 58-22-2-4-6-4-10-2-12 12-28 18-46 16z" fill="#b71c1c" />

      {BOWLS.map((b, i) => (
        <g key={i}>
          <ellipse cx={b.cx} cy={b.cy + b.r * 0.35} rx={b.r} ry={b.r * 0.55} fill="url(#bowl-wood)" />
          <ellipse cx={b.cx} cy={b.cy} rx={b.r * 0.92} ry={b.r * 0.42} fill="#5b3a20" />
          <ellipse cx={b.cx} cy={b.cy - 2} rx={b.r * 0.84} ry={b.r * 0.36} fill={`url(#powder-${i})`} />
          <ellipse cx={b.cx - b.r * 0.2} cy={b.cy - b.r * 0.12} rx={b.r * 0.3} ry={b.r * 0.1} fill="#fff" opacity="0.18" />
        </g>
      ))}

      {/* peppercorns */}
      {[
        [30, 170], [40, 176], [50, 169], [104, 176], [114, 171], [96, 170],
      ].map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r="4" fill="#2b1d14" />
      ))}
    </svg>
  )
}
