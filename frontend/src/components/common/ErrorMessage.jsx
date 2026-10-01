import { CircleAlert, RefreshCw } from 'lucide-react'
import Button from './Button'

export default function ErrorMessage({ message, onRetry, className = '' }) {
  if (!message) return null
  return (
    <div className={`error-message ${className}`} role="alert">
      <CircleAlert size={18} />
      <span>{message}</span>
      {onRetry && (
        <Button variant="ghost" size="sm" icon={RefreshCw} onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
