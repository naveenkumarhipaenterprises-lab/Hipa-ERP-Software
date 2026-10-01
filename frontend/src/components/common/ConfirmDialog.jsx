import { TriangleAlert } from 'lucide-react'
import { useState } from 'react'
import Button from './Button'
import ErrorMessage from './ErrorMessage'
import Modal from './Modal'

/**
 * Asks the user to confirm an action before it runs.
 * onConfirm may return a promise: the dialog shows progress, closes on success,
 * and shows the error (staying open) on failure.
 */
export default function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title = 'Are you sure?',
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  danger = false,
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  const cancel = () => {
    if (pending) return
    setError('')
    onClose()
  }

  const confirm = async () => {
    setPending(true)
    setError('')
    try {
      await onConfirm()
      onClose()
    } catch (e) {
      setError(e?.message || 'The action could not be completed. Please try again.')
    } finally {
      setPending(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={cancel}
      title={title}
      size="sm"
      closeOnBackdrop={!pending}
      footer={
        <>
          <Button variant="outline" onClick={cancel} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} onClick={confirm} loading={pending}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="confirm">
        {danger && <TriangleAlert size={22} className="confirm__icon" aria-hidden />}
        <div className="confirm__body">
          {message && <p>{message}</p>}
          <ErrorMessage message={error} />
        </div>
      </div>
    </Modal>
  )
}
