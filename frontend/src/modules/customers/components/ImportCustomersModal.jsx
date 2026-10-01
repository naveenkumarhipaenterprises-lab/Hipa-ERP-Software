import { CircleCheck, Download, FileSpreadsheet, Upload } from 'lucide-react'
import { useId, useState } from 'react'
import { customersApi } from '../../../api/customersApi'
import Button from '../../../components/common/Button'
import ErrorMessage from '../../../components/common/ErrorMessage'
import Modal from '../../../components/common/Modal'
import { formatNumber } from '../../../utils/formatters'

const MAX_BYTES = 5 * 1024 * 1024

/**
 * Uploads a CSV to POST /customers/import/. The backend parses and validates it;
 * this dialog only checks the file type and size, then shows the server's summary.
 */
export default function ImportCustomersModal({ open, onClose, onImported }) {
  if (!open) return null
  return <ImportDialog onClose={onClose} onImported={onImported} />
}

function ImportDialog({ onClose, onImported }) {
  const inputId = useId()
  const [file, setFile] = useState(null)
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const [result, setResult] = useState(null)
  const [templateError, setTemplateError] = useState('')

  const pick = (e) => {
    const f = e.target.files?.[0] ?? null
    setResult(null)
    setError('')
    if (f && !/\.csv$/i.test(f.name)) {
      setFile(null)
      setError('Please choose a .csv file.')
      return
    }
    if (f && f.size > MAX_BYTES) {
      setFile(null)
      setError('The file is larger than 5 MB. Split it into smaller files.')
      return
    }
    setFile(f)
  }

  const upload = async () => {
    if (!file || pending) return
    setPending(true)
    setError('')
    try {
      const res = await customersApi.importFile(file)
      setResult(res ?? {})
      onImported?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setPending(false)
    }
  }

  const template = async () => {
    setTemplateError('')
    try {
      await customersApi.downloadTemplate()
    } catch (err) {
      setTemplateError(err.message)
    }
  }

  const errors = Array.isArray(result?.errors) ? result.errors : []

  return (
    <Modal
      open
      onClose={onClose}
      title="Import Customers"
      subtitle="Upload a CSV file of customers"
      closeOnBackdrop={!pending}
      footer={
        result ? (
          <Button onClick={onClose}>Done</Button>
        ) : (
          <>
            <Button variant="outline" onClick={onClose} disabled={pending}>
              Cancel
            </Button>
            <Button icon={Upload} onClick={upload} loading={pending} disabled={!file}>
              {pending ? 'Uploading…' : 'Upload'}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="import-result" role="status">
          <CircleCheck size={28} aria-hidden />
          <div>
            <p>
              <strong>{formatNumber(result.created ?? 0)}</strong> added
              {result.updated != null && (
                <>
                  , <strong>{formatNumber(result.updated)}</strong> updated
                </>
              )}
              {result.skipped != null && (
                <>
                  , <strong>{formatNumber(result.skipped)}</strong> skipped
                </>
              )}
              .
            </p>
            {errors.length > 0 && (
              <ul className="import-result__errors">
                {errors.slice(0, 20).map((e, i) => (
                  <li key={i}>
                    {e.row != null && <strong>Row {e.row}: </strong>}
                    {e.message}
                  </li>
                ))}
                {errors.length > 20 && <li>…and {formatNumber(errors.length - 20)} more</li>}
              </ul>
            )}
          </div>
        </div>
      ) : (
        <div className="import-form">
          <p className="muted">
            Use the template so the columns match what the system expects. Rows are checked by the server before anything is saved.
          </p>
          <Button variant="soft" size="sm" icon={Download} onClick={template}>
            Download CSV template
          </Button>
          <ErrorMessage message={templateError} />

          {/* Input comes first so its keyboard focus can highlight the label (input:focus-visible + .file-drop) */}
          <input id={inputId} type="file" accept=".csv,text/csv" className="sr-only" onChange={pick} disabled={pending} />
          <label htmlFor={inputId} className={`file-drop ${file ? 'file-drop--chosen' : ''}`}>
            <FileSpreadsheet size={26} aria-hidden />
            <span>{file ? file.name : 'Choose a CSV file'}</span>
            <small>{file ? `${formatNumber(Math.ceil(file.size / 1024))} KB` : 'Maximum 5 MB'}</small>
          </label>
          <ErrorMessage message={error} />
        </div>
      )}
    </Modal>
  )
}
