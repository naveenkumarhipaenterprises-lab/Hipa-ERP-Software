import { useState } from 'react'
import { customersApi } from '../../../api/customersApi'
import ConfirmDialog from '../../../components/common/ConfirmDialog'
import EmptyState from '../../../components/common/EmptyState'
import FormModal from '../../../components/common/FormModal'
import Modal from '../../../components/common/Modal'
import OptionsGate from '../../../components/common/OptionsGate'
import { useToast } from '../../../hooks/useToast'
import { formatNumber } from '../../../utils/formatters'

const list = (v) => (Array.isArray(v) ? v : [])
const labelOf = (opts, value) => list(opts).find((o) => String(o.value) === String(value))?.label ?? value

/**
 * Two steps: write the offer, then confirm before POST /customers/offers/ sends it
 * to real customers. Segments and channels come from GET /customers/options/.
 */
export default function SendOfferModal({ open, options, onClose }) {
  const toast = useToast()
  const [draft, setDraft] = useState(null)

  if (!open && !draft) return null

  const send = async () => {
    const res = await customersApi.sendOffer(draft.values)
    toast.success(res?.queued != null ? `Offer queued for ${formatNumber(res.queued)} customers` : 'Offer queued for sending')
  }

  if (draft) {
    return (
      <ConfirmDialog
        open
        onClose={() => setDraft(null)}
        onConfirm={send}
        title="Send this offer?"
        message={`It will be sent to ${draft.segmentLabel} via ${draft.channelLabel}. Messages cannot be recalled once sent.`}
        confirmLabel="Send Offer"
        cancelLabel="Go Back"
      />
    )
  }

  return (
    <OptionsGate options={options} title="Send Offers" onClose={onClose}>
      {(data) => {
        const channels = list(data.offer_channels)
        if (channels.length === 0) {
          return (
            <Modal open onClose={onClose} title="Send Offers" size="sm">
              <EmptyState compact title="Messaging is not set up" message="No offer channels (WhatsApp, SMS or email) are connected yet. Contact your administrator." />
            </Modal>
          )
        }
        const segments = [{ value: 'all', label: 'All customers' }, ...list(data.types)]
        return (
          <FormModal
            open
            onClose={onClose}
            title="Send Offers"
            subtitle="Send a promotional message to a customer segment"
            submitLabel="Review & Send"
            fields={[
              { name: 'segment', label: 'Customer segment', type: 'select', required: true, options: segments, placeholder: 'Select segment' },
              { name: 'channel', label: 'Channel', type: 'select', required: true, options: channels, placeholder: 'Select channel' },
              { name: 'message', label: 'Message', type: 'textarea', required: true, placeholder: 'Write the offer message customers will receive' },
            ]}
            onSubmit={async (values) => {
              setDraft({
                values: { ...values, message: values.message.trim() },
                segmentLabel: values.segment === 'all' ? 'all customers' : `${labelOf(segments, values.segment)} customers`,
                channelLabel: labelOf(channels, values.channel),
              })
              onClose()
            }}
          />
        )
      }}
    </OptionsGate>
  )
}
