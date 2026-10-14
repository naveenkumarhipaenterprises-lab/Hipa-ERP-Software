import { Download, FileText, Pencil, Upload } from 'lucide-react'
import { Fragment, useEffect, useState } from 'react'
import { qualityApi } from '../../../api/qualityApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import FormModal from '../../../components/common/FormModal'
import Loader from '../../../components/common/Loader'
import Modal from '../../../components/common/Modal'
import { useToast } from '../../../hooks/useToast'
import { formatDate, todayISO } from '../../../utils/formatters'
import { STATUS_TONES, fileSize } from '../certifications'

const MAX_BYTES = 4 * 1024 * 1024 // the server refuses larger files too
const TYPES = { pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png' }
const list = (v) => (Array.isArray(v) ? v : [])

function documentError(doc) {
  const file = doc?.file
  if (!file) return undefined
  const ext = file.name.split('.').pop().toLowerCase()
  if (!(ext in TYPES)) return 'Upload a PDF, JPG, JPEG or PNG file.'
  if (file.size === 0) return 'The file is empty.'
  if (file.size > MAX_BYTES) return 'The file can be at most 4 MB.'
  return undefined
}

/** Certificate document field: choose a file (PDF / JPG / PNG, max 4 MB); when editing, keep, replace or remove the saved one. */
function DocumentInput({ value, onChange, error, current }) {
  const doc = value || {}
  return (
    <div className={`field ${error ? 'field--error' : ''}`}>
      <label className="field__label" htmlFor="certificate-document">Certificate Document</label>
      {current && !doc.file && (
        <p className="muted">
          {doc.remove ? <s>{current.name}</s> : <>Saved: <strong>{current.name}</strong> ({fileSize(current.size)})</>}
          {' '}
          <button type="button" className="link" onClick={() => onChange({ ...doc, remove: !doc.remove })}>
            {doc.remove ? 'Keep it' : 'Remove'}
          </button>
        </p>
      )}
      <input id="certificate-document" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
             aria-invalid={Boolean(error)} onChange={(e) => onChange({ file: e.target.files?.[0] ?? null, remove: false })} />
      {error ? <p className="field__error" role="alert">{error}</p>
        : <p className="field__hint">PDF, JPG, JPEG or PNG, up to 4 MB.{current ? ' Choosing a file replaces the saved one.' : ''}</p>}
    </div>
  )
}

/** Add or edit a certification; the document is uploaded with the details in one save. */
export function CertificationFormModal({ editing, options, onClose, onSaved }) {
  const toast = useToast()
  if (!editing) return null
  const c = editing.certification
  const fields = [
    { name: 'name', label: 'Certification Name', required: true, full: true, placeholder: 'e.g. FSSAI License' },
    { name: 'issuing_authority', label: 'Issuing Authority / Organization' },
    { name: 'certificate_number', label: 'Certificate Number' },
    { name: 'category', label: 'Category', type: 'select', placeholder: 'Choose category', options: list(options?.certification_categories) },
    { name: 'status', label: 'Certification Status', type: 'select', required: true, options: list(options?.certification_statuses) },
    { name: 'issue_date', label: 'Issue Date', type: 'date', validate: (v) => (v > todayISO() ? 'The issue date can\'t be in the future' : undefined) },
    { name: 'valid_until', label: 'Expiry Date', type: 'date',
      validate: (v, all) => (all.issue_date && v < all.issue_date ? 'The expiry date can\'t be before the issue date' : undefined) },
    { name: 'document', label: 'Certificate Document', validate: documentError,
      render: (field) => <DocumentInput {...field} current={c?.document} /> },
    { name: 'notes', label: 'Description / Notes', type: 'textarea' },
  ]
  const save = async ({ document, ...values }) => {
    const body = { ...values, document: document?.file ?? null, removeDocument: Boolean(document?.remove) }
    const saved = c ? await qualityApi.updateCertification(c.id, body) : await qualityApi.createCertification(body)
    toast.success(c ? `${saved.name} updated` : `${saved.name} added`)
    onSaved()
  }
  return (
    <FormModal
      open
      onClose={onClose}
      title={c ? `Edit ${c.name}` : 'Add Certification'}
      subtitle="Food safety and quality certificates. The document is stored securely with the details."
      fields={fields}
      initialValues={c ? {
        name: c.name, issuing_authority: c.issuing_authority ?? '', certificate_number: c.certificate_number ?? '',
        category: c.category_value ?? '', status: c.status_value, issue_date: c.issue_date ?? '', valid_until: c.valid_until ?? '',
        notes: c.notes ?? '', document: null,
      } : { status: 'active', document: null }}
      submitLabel={c ? 'Save Changes' : 'Save Certification'}
      onSubmit={save}
    />
  )
}

/** Shows a stored certificate (PDF in a frame, image as a picture), fetched with the user's sign-in. */
export function DocumentPreviewModal({ certification, onClose }) {
  const [state, setState] = useState({ url: null, error: null })
  const toast = useToast()
  const id = certification?.id
  useEffect(() => {
    if (!id) return undefined
    let url = null
    let active = true
    qualityApi.getCertificationDocument(id).then(
      (blob) => {
        url = URL.createObjectURL(blob)
        if (active) setState({ url, error: null })
        else URL.revokeObjectURL(url)
      },
      (error) => active && setState({ url: null, error }),
    )
    return () => {
      active = false
      if (url) URL.revokeObjectURL(url)
      setState({ url: null, error: null })
    }
  }, [id])
  if (!certification) return null
  const doc = certification.document
  const download = () => qualityApi.downloadCertificationDocument(certification.id, doc.name).catch((err) => toast.error(err.message))
  return (
    <Modal open onClose={onClose} title={doc.name} subtitle={certification.name} size="xl"
           footer={<Button variant="outline" icon={Download} onClick={download}>Download</Button>}>
      {state.error ? (
        <ErrorMessage message={state.error.message} />
      ) : !state.url ? (
        <Loader label="Loading certificate…" />
      ) : doc.type === 'application/pdf' ? (
        <iframe className="pdf-frame" title={doc.name} src={state.url} />
      ) : (
        <img className="cert-image" src={state.url} alt={`Certificate: ${certification.name}`} />
      )}
    </Modal>
  )
}

/** All saved details of one certification. */
export function CertificationViewModal({ certification, canManage, onClose, onEdit, onOpenDocument }) {
  if (!certification) return null
  const c = certification
  const rows = [
    ['Issuing Authority', c.issuing_authority], ['Certificate Number', c.certificate_number], ['Category', c.category],
    ['Issue Date', c.issue_date && formatDate(c.issue_date)], ['Expiry Date', c.valid_until && formatDate(c.valid_until)],
    ['Status', c.status && <Badge tone={STATUS_TONES[c.status]}>{c.status}</Badge>], ['Notes', c.notes],
  ]
  return (
    <Modal open onClose={onClose} title={c.name} subtitle={c.category ?? 'Certification'}
           footer={canManage ? <Button variant="outline" icon={Pencil} onClick={onEdit}>Edit</Button> : undefined}>
      <dl className="detail-list">
        {rows.map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{v || '—'}</dd></Fragment>)}
        <dt>Certificate</dt>
        <dd>
          {c.document ? (
            <Button size="sm" variant="outline" icon={FileText} onClick={onOpenDocument}>
              {c.document.name} ({fileSize(c.document.size)})
            </Button>
          ) : canManage ? (
            <Button size="sm" variant="ghost" icon={Upload} onClick={onEdit}>Upload certificate</Button>
          ) : '—'}
        </dd>
      </dl>
    </Modal>
  )
}
