import { Award, Eye, FileText, Pencil, Plus, Trash2, Upload } from 'lucide-react'
import { useState } from 'react'
import { qualityApi } from '../../../api/qualityApi'
import Badge from '../../../components/common/Badge'
import Button from '../../../components/common/Button'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import { useToast } from '../../../hooks/useToast'
import { formatDate } from '../../../utils/formatters'
import { STATUS_TONES } from '../certifications'
import { CertificationFormModal, CertificationViewModal, DocumentPreviewModal } from './CertificationForms'

/** "Add Certification" for the card's title row (quality managers only; the server checks too). */
export function AddCertificationButton({ onClick }) {
  return <Button size="sm" icon={Plus} onClick={onClick}>Add Certification</Button>
}

/**
 * Certifications held, from the API (overview.certifications), with view / add / edit / delete and the stored
 * certificate document. `adding` / `onAddDone` let the card's own Add button open the same form.
 */
export default function Certifications({ items, options, canManage, adding, onAddDone, onChanged }) {
  const toast = useToast()
  const [editing, setEditing] = useState(null) // { certification? }
  const [viewing, setViewing] = useState(null)
  const [previewing, setPreviewing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const rows = Array.isArray(items) ? items : []
  const form = adding ? {} : editing

  const closeForm = () => {
    setEditing(null)
    onAddDone?.()
  }
  const saved = () => {
    setViewing(null)
    onChanged()
  }
  const remove = async () => {
    await qualityApi.deleteCertification(deleting.id)
    toast.success(`${deleting.name} deleted`)
    onChanged()
  }

  return (
    <>
      {rows.length === 0 ? (
        <EmptyState
          compact
          icon={Award}
          title="No certifications recorded"
          message={canManage ? 'Add your food safety and quality certifications and upload each certificate (PDF, JPG or PNG).'
            : 'Food safety and quality certifications will be listed here.'}
          action={canManage && (
            <span className="row-actions">
              <Button size="sm" icon={Plus} onClick={() => setEditing({})}>Add Certification</Button>
              <Button size="sm" variant="outline" icon={Upload} onClick={() => setEditing({})}>Upload Certificate</Button>
            </span>
          )}
        />
      ) : (
        <ul className="cert-list">
          {rows.map((c) => (
            <li key={c.id} className="cert-list__item">
              <Award size={26} aria-hidden />
              <div>
                <strong>{c.name}</strong>
                {(c.issuing_authority || c.certificate_number || c.detail) && (
                  <span>{[c.issuing_authority, c.certificate_number && `No. ${c.certificate_number}`].filter(Boolean).join(' · ') || c.detail}</span>
                )}
                {(c.issue_date || c.valid_until) && (
                  <small>
                    {[c.issue_date && `Issued ${formatDate(c.issue_date)}`, c.valid_until && `Valid until ${formatDate(c.valid_until)}`].filter(Boolean).join(' · ')}
                  </small>
                )}
                <small>{c.document ? `Certificate: ${c.document.name}` : 'No certificate uploaded'}</small>
                <span className="row-actions cert-list__actions">
                  {c.document && <Button size="sm" variant="ghost" icon={FileText} onClick={() => setPreviewing(c)} aria-label={`Open certificate of ${c.name}`} />}
                  <Button size="sm" variant="ghost" icon={Eye} onClick={() => setViewing(c)} aria-label={`View ${c.name}`} />
                  {canManage && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setEditing({ certification: c })} aria-label={`Edit ${c.name}`} />}
                  {canManage && <Button size="sm" variant="ghost" icon={Trash2} className="btn--tone-red" onClick={() => setDeleting(c)} aria-label={`Delete ${c.name}`} />}
                </span>
              </div>
              {c.status && <Badge tone={STATUS_TONES[c.status]}>{c.status}</Badge>}
            </li>
          ))}
        </ul>
      )}

      <CertificationFormModal editing={form} options={options} onClose={closeForm} onSaved={saved} />
      <CertificationViewModal
        certification={viewing}
        canManage={canManage}
        onClose={() => setViewing(null)}
        onEdit={() => { setEditing({ certification: viewing }); setViewing(null) }}
        onOpenDocument={() => setPreviewing(viewing)}
      />
      <DocumentPreviewModal certification={previewing} onClose={() => setPreviewing(null)} />
      <ConfirmDialog
        open={Boolean(deleting)}
        onClose={() => setDeleting(null)}
        onConfirm={remove}
        danger
        title="Delete certification?"
        message={deleting ? `Delete ${deleting.name}${deleting.document ? ' and its uploaded certificate' : ''}? This can't be undone.` : ''}
        confirmLabel="Delete"
        cancelLabel="Keep"
      />
    </>
  )
}
