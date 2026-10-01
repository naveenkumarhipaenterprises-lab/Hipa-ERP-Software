import ErrorMessage from './ErrorMessage'
import Loader from './Loader'
import Modal from './Modal'

/**
 * For forms whose choices come from the API (customers, products, types…):
 * shows a loading or error modal until `options` (a useApi result) has data,
 * then renders `children(options.data)`.
 */
export default function OptionsGate({ options, title, onClose, loadingLabel = 'Loading…', children }) {
  if (options.data && !options.error) return children(options.data)
  return (
    <Modal open onClose={onClose} title={title} size="sm">
      {options.error && !options.loading ? (
        <ErrorMessage message={options.error.message} onRetry={options.reload} />
      ) : (
        <Loader label={loadingLabel} />
      )}
    </Modal>
  )
}
