import { Download, FileText, Trash2, Upload } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { attendanceApi } from '../../../api/attendanceApi'
import Button from '../../../components/common/Button'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Modal from '../../../components/common/Modal'
import { useApi } from '../../../hooks/useApi'
import { useToast } from '../../../hooks/useToast'
import { formatDate } from '../../../utils/formatters'
import { list } from '../shared'

const PHOTO_ACCEPT = '.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp'
const DOC_ACCEPT = PHOTO_ACCEPT + ',.pdf,.doc,.docx,.xls,.xlsx,application/pdf'

const sizeLabel = (bytes) => (bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`)

/**
 * The photo and documents kept on one employee's record (Attendance → Employees → Files).
 * Uploading needs Manage Employees (or being that employee); deleting a file is for Super Admins.
 */
export default function EmployeeFilesModal({ employee, canManage, canDelete, onClose }) {
  const toast = useToast()
  const [refreshKey, setRefreshKey] = useState(0)
  const [busy, setBusy] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [photoUrl, setPhotoUrl] = useState(null)
  const photoInput = useRef(null)
  const docInput = useRef(null)

  const files = useApi(() => attendanceApi.listEmployeeFiles(employee.id), [employee.id, refreshKey])
  const rows = list(files.data?.results)
  const photo = rows.find((f) => f.kind === 'photo')
  const documents = rows.filter((f) => f.kind !== 'photo')

  useEffect(() => {
    if (!photo) return undefined
    let url
    let cancelled = false
    attendanceApi.getEmployeeFile(employee.id, photo.id).then((blob) => {
      url = URL.createObjectURL(blob)
      if (!cancelled) setPhotoUrl(url)
    }).catch(() => {})
    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [employee.id, photo?.id]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file, kind) => {
    if (!file) return
    setBusy(true)
    try {
      await attendanceApi.uploadEmployeeFile(employee.id, file, kind)
      toast.success(kind === 'photo' ? 'Photo saved' : `${file.name} uploaded`)
      setRefreshKey((k) => k + 1)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setBusy(false)
      if (photoInput.current) photoInput.current.value = ''
      if (docInput.current) docInput.current.value = ''
    }
  }

  const remove = async () => {
    await attendanceApi.deleteEmployeeFile(employee.id, deleting.id)
    toast.success(`${deleting.name} deleted`)
    setRefreshKey((k) => k + 1)
  }

  return (
    <Modal open onClose={onClose} title={`${employee.name} — Photo & Documents`} subtitle={employee.employee_code}>
      <div className="employee-files">
        <div className="employee-files__photo">
          {photo && photoUrl ? <img src={photoUrl} alt={`Photo of ${employee.name}`} /> : <span className="employee-files__nophoto" aria-hidden>No photo</span>}
          {canManage && (
            <>
              <input ref={photoInput} id="employee-photo" type="file" accept={PHOTO_ACCEPT} className="sr-only"
                     onChange={(e) => upload(e.target.files?.[0], 'photo')} />
              <Button size="sm" variant="soft" icon={Upload} disabled={busy} onClick={() => photoInput.current?.click()}>
                {photo ? 'Change photo' : 'Add photo'}
              </Button>
            </>
          )}
        </div>

        <div className="employee-files__docs">
          <div className="employee-files__head">
            <strong>Documents</strong>
            {canManage && (
              <>
                <input ref={docInput} id="employee-document" type="file" accept={DOC_ACCEPT} className="sr-only"
                       onChange={(e) => upload(e.target.files?.[0], 'document')} />
                <Button size="sm" icon={Upload} disabled={busy} onClick={() => docInput.current?.click()}>Upload document</Button>
              </>
            )}
          </div>
          {files.error && !files.loading ? (
            <ErrorMessage message={files.error.message} onRetry={files.reload} />
          ) : documents.length === 0 ? (
            <p className="muted">{files.loading ? 'Loading…' : 'No documents yet. ID proofs, certificates and contracts go here (PDF, images, Word or Excel, up to 5 MB each).'}</p>
          ) : (
            <ul className="employee-files__list">
              {documents.map((f) => (
                <li key={f.id}>
                  <FileText size={16} aria-hidden />
                  <span className="employee-files__name">
                    <strong>{f.name}</strong>
                    <small className="muted">{sizeLabel(f.size)} · {formatDate(f.uploaded_at)}{f.uploaded_by ? ` · ${f.uploaded_by}` : ''}</small>
                  </span>
                  <span className="row-actions">
                    <Button size="sm" variant="ghost" icon={Download} aria-label={`Download ${f.name}`}
                            onClick={() => attendanceApi.downloadEmployeeFile(employee.id, f.id, f.name)} />
                    {canDelete && (
                      <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" aria-label={`Delete ${f.name}`}
                              onClick={() => setDeleting(f)} />
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        danger
        title="Delete this document?"
        message={deleting && `${deleting.name} will be removed from ${employee.name}'s record.`}
        confirmLabel="Delete"
        cancelLabel="Keep"
      />
    </Modal>
  )
}
