import { ShoppingCart } from 'lucide-react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { purchaseApi } from '../../api/purchaseApi'
import DateRangeSelect from '../../components/common/DateRangeSelect'
import PageHeader from '../../components/common/PageHeader'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { useToast } from '../../hooks/useToast'
import { DATE_RANGES, hasAnyRole, NAV_ITEMS } from '../../utils/constants'
import MaterialsPanel from './components/MaterialsPanel'
import PurchaseFormModal from './components/PurchaseFormModal'
import PurchaseOverview from './components/PurchaseOverview'
import PurchasesPanel from './components/PurchasesPanel'
import RecommendationsPanel from './components/RecommendationsPanel'
import { GoodsReceiptModal, PurchaseReturnModal, SupplierPaymentModal } from './components/RecordModals'
import { PaymentsPanel, ReceiptsPanel, ReturnsPanel } from './components/RecordsPanels'
import SuppliersPanel from './components/SuppliersPanel'
import { list, PAYMENT_MANAGERS, PURCHASE_MANAGERS, STOCK_RECORDERS } from './shared'

// The same sections as the sidebar sub-menu
const TABS = NAV_ITEMS.find((n) => n.key === 'purchase').children

export default function PurchasePage() {
  const { user } = useAuth()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [range, setRange] = useState(DATE_RANGES[0].value)
  const [refreshKey, setRefreshKey] = useState(0)
  const [modal, setModal] = useState(null) // { kind: 'purchase'|'receipt'|'return'|'payment', purchase?, prefill? }

  const canManage = hasAnyRole(user, PURCHASE_MANAGERS)
  const canPay = hasAnyRole(user, PAYMENT_MANAGERS)
  const canRecordUsage = hasAnyRole(user, STOCK_RECORDERS)
  const tab = TABS.some((t) => t.tab === params.get('tab')) ? params.get('tab') : TABS[0].tab
  const options = useApi(() => purchaseApi.getOptions(), [refreshKey])
  const rangeLabel = DATE_RANGES.find((r) => r.value === range)?.label ?? ''

  const refresh = () => setRefreshKey((k) => k + 1)
  const close = () => setModal(null)
  const selectTab = (key) => setParams(key === TABS[0].tab ? {} : { tab: key }, { replace: true })

  const savePurchase = async (body) => {
    const p = modal.purchase ? await purchaseApi.updatePurchase(modal.purchase.id, body) : await purchaseApi.createPurchase(body)
    toast.success(modal.purchase ? `${p.purchase_number} updated` : `Purchase ${p.purchase_number} recorded: ${p.item}`)
    refresh()
  }
  const saveReceipt = async (body) => {
    const g = await purchaseApi.createGoodsReceipt(body)
    toast.success(`${g.grn_number} recorded: ${g.accepted_quantity} ${g.unit} accepted into stock`)
    refresh()
  }
  const saveReturn = async (body) => {
    const r = await purchaseApi.createReturn(body)
    toast.success(`Return ${r.return_number} recorded`)
    refresh()
  }
  const savePayment = async (body) => {
    const p = await purchaseApi.createPayment(body)
    toast.success(`${p.payment_number} recorded (${p.status})`)
    refresh()
  }

  // "Buy" on an AI recommendation opens a purchase pre-filled with the item, quantity and cheapest recent supplier
  const buy = (r) => {
    const supplier = list(options.data?.suppliers).find((s) => s.name === (r.best_supplier ?? r.preferred_supplier))
    setModal({
      kind: 'purchase',
      prefill: {
        item_type: r.item_type,
        material_id: r.item_type === 'material' ? r.item_id : undefined,
        product_id: r.item_type === 'product' ? r.item_id : undefined,
        quantity: r.recommended_quantity,
        supplier_id: supplier?.id,
      },
    })
  }

  const panelProps = { options, canManage, refreshKey, onChanged: refresh }

  return (
    <div className="page">
      <title>Purchase | HIPA MASALA</title>
      <PageHeader icon={ShoppingCart} title="Purchase" subtitle="Suppliers, raw materials, purchases, goods receipts, returns and supplier payments">
        {tab === 'overview' && <DateRangeSelect value={range} onChange={setRange} />}
      </PageHeader>

      <div className="tabs" role="tablist" aria-label="Purchase sections">
        {TABS.map((t) => (
          <button
            key={t.tab}
            type="button"
            role="tab"
            id={`purchase-tab-${t.tab}`}
            aria-selected={tab === t.tab}
            aria-controls="purchase-tabpanel"
            className={`tabs__tab ${tab === t.tab ? 'tabs__tab--active' : ''}`}
            tabIndex={tab === t.tab ? 0 : -1}
            onClick={() => selectTab(t.tab)}
            onKeyDown={(e) => {
              if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return
              const i = TABS.findIndex((x) => x.tab === tab)
              const next = TABS[(i + (e.key === 'ArrowRight' ? 1 : TABS.length - 1)) % TABS.length].tab
              selectTab(next)
              document.getElementById(`purchase-tab-${next}`)?.focus()
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="stack" role="tabpanel" id="purchase-tabpanel" aria-labelledby={`purchase-tab-${tab}`}>
        {tab === 'overview' && <PurchaseOverview range={range} rangeLabel={rangeLabel} refreshKey={refreshKey} />}
        {tab === 'purchases' && (
          <PurchasesPanel
            {...panelProps}
            canPay={canPay}
            onNew={() => setModal({ kind: 'purchase' })}
            onEdit={(p) => setModal({ kind: 'purchase', purchase: p })}
            onReceive={(p) => setModal({ kind: 'receipt', purchase: p })}
            onPay={(p) => setModal({ kind: 'payment', purchase: p })}
            onReturn={(p) => setModal({ kind: 'return', purchase: p })}
          />
        )}
        {tab === 'receipts' && <ReceiptsPanel {...panelProps} onNew={() => setModal({ kind: 'receipt' })} />}
        {tab === 'returns' && <ReturnsPanel {...panelProps} onNew={() => setModal({ kind: 'return' })} />}
        {tab === 'payments' && <PaymentsPanel {...panelProps} canPay={canPay} onNew={() => setModal({ kind: 'payment' })} />}
        {tab === 'suppliers' && <SuppliersPanel {...panelProps} />}
        {tab === 'materials' && <MaterialsPanel {...panelProps} canRecordUsage={canRecordUsage} />}
        {tab === 'recommendations' && <RecommendationsPanel canManage={canManage} onBuy={buy} />}
      </div>

      <PurchaseFormModal open={modal?.kind === 'purchase'} purchase={modal?.purchase} prefill={modal?.prefill} options={options} onClose={close} onSave={savePurchase} />
      <GoodsReceiptModal open={modal?.kind === 'receipt'} purchase={modal?.purchase} options={options} onClose={close} onSave={saveReceipt} />
      <PurchaseReturnModal open={modal?.kind === 'return'} purchase={modal?.purchase} options={options} onClose={close} onSave={saveReturn} />
      <SupplierPaymentModal open={modal?.kind === 'payment'} purchase={modal?.purchase} options={options} onClose={close} onSave={savePayment} />
    </div>
  )
}
