import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { recordsApi } from '../../api/recordsApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { isSuperAdmin } from '../../utils/constants'
import Button from './Button'
import ConfirmDialog from './ConfirmDialog'

/**
 * Delete for a wrong entry (Super Admins only; nothing is shown to anyone else). The server removes the entry as if it
 * was never made: stock and paid / received totals are put back. If other records still depend on it, the dialog
 * shows what to delete first.
 *   <DeleteRecordButton kind="sales_invoice" id={row.id} label={row.invoice_number} onDeleted={reload} />
 */
export default function DeleteRecordButton({ kind, id, label, onDeleted, size = 'sm' }) {
  const { user } = useAuth()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  if (!isSuperAdmin(user) || !id) return null

  const remove = async () => {
    await recordsApi.remove(kind, id)
    toast.success(`${label} deleted`)
    onDeleted?.()
  }

  return (
    <>
      <Button size={size} variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => setOpen(true)} aria-label={`Delete ${label}`} />
      <ConfirmDialog
        open={open}
        onClose={() => setOpen(false)}
        onConfirm={remove}
        danger
        title={`Delete ${label}?`}
        message="This removes the entry as if it was never made. Stock and paid amounts it changed are put back. This can't be undone."
        confirmLabel="Delete"
      />
    </>
  )
}
