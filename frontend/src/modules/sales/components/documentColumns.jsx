import { money, qty } from '../../../utils/display'

/** Product-line columns shared by quotation, order and invoice details. */
export const ITEM_COLUMNS = [
  { key: 'product', header: 'Product', render: (r) => <strong>{r.product}</strong> },
  { key: 'quantity_kg', header: 'Quantity', align: 'right', render: (r) => qty(r.quantity_kg, 'kg') },
  { key: 'unit_price', header: 'Unit Price', align: 'right', render: (r) => money(r.unit_price) },
  { key: 'discount_pct', header: 'Discount', align: 'right', render: (r) => `${r.discount_pct}%` },
  { key: 'gst_pct', header: 'GST', align: 'right', render: (r) => `${r.gst_pct}%` },
  { key: 'amount', header: 'Amount', align: 'right', render: (r) => money(r.amount) },
]
