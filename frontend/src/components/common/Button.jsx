import { LoaderCircle } from 'lucide-react'

/**
 * variant: primary | secondary | outline | ghost | danger | soft
 * size: sm | md | lg
 */
export default function Button({
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconRight: IconRight,
  loading = false,
  block = false,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}) {
  const classes = ['btn', `btn--${variant}`, `btn--${size}`, block && 'btn--block', className]
    .filter(Boolean)
    .join(' ')
  const iconSize = size === 'sm' ? 15 : 18

  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <LoaderCircle size={iconSize} className="spin" /> : Icon && <Icon size={iconSize} />}
      {children && <span>{children}</span>}
      {IconRight && !loading && <IconRight size={iconSize} />}
    </button>
  )
}
