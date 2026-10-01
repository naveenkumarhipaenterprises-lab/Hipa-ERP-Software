import hipaLogo from '../../assets/logos/hipa-logo.png'

/**
 * The official HIPA MASALA logo: the original "Hipa logo.png" image, shown exactly as supplied.
 * It is never redrawn, recoloured or cropped; `size` only scales it, keeping its square proportions.
 * This is the only place the logo is rendered.
 */
export default function Logo({ size = 120, className = '' }) {
  return (
    <img
      src={hipaLogo}
      alt="HIPA MASALA"
      width={size}
      height={size}
      className={`logo ${className}`.trim()}
      decoding="async"
      draggable={false}
    />
  )
}
