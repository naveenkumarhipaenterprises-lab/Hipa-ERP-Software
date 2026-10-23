import { MapPin } from 'lucide-react'

/**
 * Where someone checked in or out (a { latitude, longitude, accuracy, address, map_url } block from the server):
 * the street address, or the coordinates while no address is known, opening the exact spot in Google Maps.
 * compact: one shortened line for tables (the full address shows on hover).
 */
export default function LocationLink({ location, compact = false, manual = false }) {
  if (!location) return <span className="muted">{manual ? 'Manual entry' : '—'}</span>
  const coords = `${location.latitude.toFixed(6)}, ${location.longitude.toFixed(6)}`
  const text = location.address || coords
  const accuracy = location.accuracy != null ? `±${location.accuracy} m` : null
  return (
    <a className={`location-link${compact ? ' location-link--compact' : ''}`} href={location.map_url} target="_blank" rel="noopener noreferrer"
       title={`${text}${location.address ? ` (${coords})` : ''}${accuracy ? ` · accurate to ${accuracy}` : ''} — open in Google Maps`}>
      <MapPin size={14} aria-hidden />
      <span className="location-link__text">{text}</span>
      {accuracy && !compact && <span className="muted location-link__accuracy">{accuracy}</span>}
    </a>
  )
}
