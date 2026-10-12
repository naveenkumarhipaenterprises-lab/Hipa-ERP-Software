"""
Super Admin deletes: remove a wrong entry as if it was never made.

Every delete runs in one transaction and
- puts back the stock the entry moved (its stock movements are removed and the product / raw-material stock adjusted),
- recalculates what depends on it (an invoice's paid amount, a purchase's received / paid amounts),
- refuses, with a message saying what to delete first, while other records still depend on it
  (e.g. an invoice that still has payments, a goods receipt that has a quality test).

Only Super Admins reach this (apps/core/views.DeleteRecordView checks the role; ModulePermission blocks DELETE too).
"""
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.db.models import ProtectedError
from rest_framework.exceptions import NotFound, ValidationError

ZERO = Decimal("0")


def _refuse(message):
    raise ValidationError({"detail": message})


def _names(objs, attr):
    items = [getattr(o, attr) for o in objs[:5]]
    return ", ".join(items) + (" …" if len(objs) > 5 else "")


def _undo_product_movements(reference, sources):
    """Removes the product stock movements an entry made and puts the stock back."""
    from apps.inventory.models import Product, StockMovement

    moves = list(StockMovement.objects.filter(reference=reference, source__in=sources))
    net = defaultdict(lambda: ZERO)  # stock the entry added, per product
    for m in moves:
        net[m.product_id] += m.quantity_kg if m.type == StockMovement.Type.IN else -m.quantity_kg
    for product in Product.objects.select_for_update(of=("self",)).filter(pk__in=net):
        added = net[product.pk]
        if added > product.stock_kg:
            _refuse(f"Only {product.stock_kg.normalize():f} kg of {product.name} is left, so the "
                    f"{added.normalize():f} kg this entry added can't be taken back. Correct the stock first.")
        product.stock_kg -= added
        product.save(update_fields=["stock_kg", "updated_at"])
    StockMovement.objects.filter(pk__in=[m.pk for m in moves]).delete()


def _undo_material_movements(reference, sources):
    """Removes the raw-material movements an entry made and puts the stock back."""
    from apps.purchase.models import MaterialMovement, RawMaterial
    from apps.purchase.services import qty_text

    moves = list(MaterialMovement.objects.filter(reference=reference, source__in=sources))
    net = defaultdict(lambda: ZERO)
    for m in moves:
        net[m.material_id] += m.quantity if m.type == MaterialMovement.Type.IN else -m.quantity
    for material in RawMaterial.objects.select_for_update(of=("self",)).filter(pk__in=net):
        added = net[material.pk]
        if added > material.current_stock:
            _refuse(f"Only {qty_text(material.current_stock, material.unit)} of {material.name} is left, so the "
                    f"{qty_text(added, material.unit)} this entry added can't be taken back. Correct the stock first.")
        material.current_stock -= added
        material.save(update_fields=["current_stock", "updated_at"])
    MaterialMovement.objects.filter(pk__in=[m.pk for m in moves]).delete()


def _delete(obj, what):
    try:
        obj.delete()
    except ProtectedError as exc:
        kinds = sorted({o._meta.verbose_name_plural for o in exc.protected_objects})
        _refuse(f"This {what} is still used by other records ({', '.join(kinds)}). Delete those first.")


# --- Sales -----------------------------------------------------------------------------------------

def sales_quotation(q):
    _delete(q, "quotation")  # orders / invoices made from it keep working (their link is cleared)
    return q.quotation_number


def sales_order(order):
    from apps.inventory.models import StockMovement as SM

    invoices = list(order.invoices.all())
    if invoices:
        _refuse(f"This order has invoice {_names(invoices, 'invoice_number')}. Delete the invoice first.")
    _undo_product_movements(order.order_number, [SM.Source.SALE, SM.Source.SALE_CANCEL])
    _delete(order, "order")
    return order.order_number


def sales_invoice(inv):
    from apps.inventory.models import StockMovement as SM

    payments, returns = list(inv.payments.all()), list(inv.returns.all())
    if payments:
        _refuse(f"This invoice has payment {_names(payments, 'receipt_number')}. Delete the payments first.")
    if returns:
        _refuse(f"This invoice has return {_names(returns, 'return_number')}. Delete the returns first.")
    _undo_product_movements(inv.invoice_number, [SM.Source.INVOICE, SM.Source.INVOICE_CANCEL])
    _delete(inv, "invoice")
    return inv.invoice_number


def sales_payment(p):
    from apps.sales.models import SalesInvoice
    from apps.sales.services import refresh_invoice_money

    invoice = SalesInvoice.objects.select_for_update(of=("self",)).get(pk=p.invoice_id)
    _drop_finance_entries(sales_payment=p)
    _delete(p, "payment")
    refresh_invoice_money(invoice)
    return p.receipt_number


def sales_return(r):
    from apps.inventory.models import StockMovement as SM
    from apps.sales.models import SalesInvoice
    from apps.sales.services import refresh_invoice_money

    invoice = SalesInvoice.objects.select_for_update(of=("self",)).get(pk=r.invoice_id)
    _undo_product_movements(r.return_number, [SM.Source.SALE_RETURN, SM.Source.SALE_RETURN_CANCEL])
    _delete(r, "return")
    refresh_invoice_money(invoice)
    return r.return_number


def customer(c):
    for rel, label in (("quotations", "quotations"), ("orders", "orders"), ("invoices", "invoices"), ("payments", "payments"),
                       ("returns", "returns")):
        if getattr(c, rel).exists():
            _refuse(f"{c.name} has sales {label}. Delete those first, or set the customer to Inactive instead.")
    _delete(c, "customer")
    return c.name


# --- Purchase ----------------------------------------------------------------------------------

def purchase(p):
    for rel, label, attr in (("goods_receipts", "goods receipt", "grn_number"), ("payments", "payment", "payment_number"),
                             ("returns", "return", "return_number")):
        found = list(getattr(p, rel).all())
        if found:
            _refuse(f"This purchase has {label} {_names(found, attr)}. Delete it first.")
    _delete(p, "purchase")  # shipments for it stay, without the link
    return p.purchase_number


def goods_receipt(grn):
    from apps.inventory.models import StockMovement as SM
    from apps.purchase.models import MaterialMovement as MM
    from apps.purchase.models import Purchase
    from apps.purchase.services import refresh_receipt_status

    if grn.quality_tests.exists():
        _refuse(f"{grn.grn_number} has a quality test. Delete the quality test first.")
    p = Purchase.objects.select_for_update(of=("self",)).get(pk=grn.purchase_id)
    _undo_product_movements(grn.grn_number, [SM.Source.PURCHASE])
    _undo_material_movements(grn.grn_number, [MM.Source.GOODS_RECEIPT])
    _delete(grn, "goods receipt")
    refresh_receipt_status(p)
    return grn.grn_number


def purchase_return(r):
    from apps.inventory.models import StockMovement as SM
    from apps.purchase.models import MaterialMovement as MM
    from apps.purchase.models import Purchase
    from apps.purchase.services import refresh_money

    p = Purchase.objects.select_for_update(of=("self",)).get(pk=r.purchase_id) if r.purchase_id else None
    _undo_product_movements(r.return_number, [SM.Source.PURCHASE_RETURN, SM.Source.RETURN_CANCEL])
    _undo_material_movements(r.return_number, [MM.Source.PURCHASE_RETURN, MM.Source.RETURN_CANCEL])
    _delete(r, "return")
    if p:
        refresh_money(p)
    return r.return_number


def supplier_payment(pm):
    from apps.purchase.models import Purchase
    from apps.purchase.services import refresh_money

    p = Purchase.objects.select_for_update(of=("self",)).get(pk=pm.purchase_id) if pm.purchase_id else None
    _drop_finance_entries(supplier_payment=pm)
    _delete(pm, "payment")
    if p:
        refresh_money(p)
    return pm.payment_number


def supplier(s):
    for rel, label in (("purchases", "purchases"), ("payments", "payments"), ("returns", "returns"), ("shipments", "shipments")):
        if getattr(s, rel).exists():
            _refuse(f"{s.name} has {label}. Delete those first, or set the supplier to Inactive instead.")
    _delete(s, "supplier")
    return s.name


def raw_material(m):
    from apps.purchase.services import UNDOABLE_MATERIAL

    if m.movements.exclude(source__in=UNDOABLE_MATERIAL).exists() or m.purchases.exists() or m.returns.exists():
        _refuse(f"{m.name} has purchases, goods receipts or returns. Delete those first, or set it to Inactive instead.")
    m.movements.all().delete()  # only hand entries are left (opening stock, usage, adjustments)
    _delete(m, "raw material")
    return m.name


def material_movement(mv):
    from apps.purchase.services import undo_material_movement

    label = f"{mv.material.name} {mv.get_type_display()} {mv.quantity.normalize():f} {mv.material.unit}"
    undo_material_movement(mv)
    return label


# --- Inventory -----------------------------------------------------------------------------------

def product(p):
    from apps.inventory.services import UNDOABLE

    if p.movements.exclude(source__in=UNDOABLE).exists():
        _refuse(f"{p.name} has sales or purchase stock movements. Delete those entries first, or set it to Inactive instead.")
    p.movements.all().delete()  # only hand entries are left (opening stock, manual in / out)
    _delete(p, "product")
    return p.name


def stock_movement(m):
    from apps.inventory.services import undo_movement

    label = f"{m.product.name} {m.get_type_display()} {m.quantity_kg.normalize():f} kg"
    undo_movement(m)
    return label


# --- Other modules -------------------------------------------------------------------------------

def plain(what, label):
    def handler(obj):
        name = label(obj)
        _delete(obj, what)
        return name
    return handler


def _drop_finance_entries(**lookup):
    """The retired Accounts module kept a copy of each payment; it goes with the payment."""
    from apps.finance.models import Transaction

    Transaction.objects.filter(**lookup).delete()


def _models():
    from apps.attendance.models import AttendanceRecord, LeaveRequest, OfficeHoliday
    from apps.customers.models import Customer
    from apps.inventory.models import Product, StockMovement
    from apps.marketing.models import Campaign, ScheduledPost
    from apps.purchase.models import GoodsReceipt, MaterialMovement, Purchase, PurchaseReturn, RawMaterial, Supplier, SupplierPayment
    from apps.quality.models import QualityAudit, QualityTest
    from apps.sales.models import SalesInvoice, SalesOrder, SalesPayment, SalesQuotation, SalesReturn
    from apps.supply_chain.models import Shipment

    return {
        # kind: (model, module, handler)
        "sales_quotation": (SalesQuotation, "sales", sales_quotation),
        "sales_order": (SalesOrder, "sales", sales_order),
        "sales_invoice": (SalesInvoice, "sales", sales_invoice),
        "sales_payment": (SalesPayment, "sales", sales_payment),
        "sales_return": (SalesReturn, "sales", sales_return),
        "customer": (Customer, "customers", customer),
        "purchase": (Purchase, "purchase", purchase),
        "goods_receipt": (GoodsReceipt, "purchase", goods_receipt),
        "purchase_return": (PurchaseReturn, "purchase", purchase_return),
        "supplier_payment": (SupplierPayment, "purchase", supplier_payment),
        "supplier": (Supplier, "purchase", supplier),
        "raw_material": (RawMaterial, "purchase", raw_material),
        "material_movement": (MaterialMovement, "purchase", material_movement),
        "product": (Product, "inventory", product),
        "stock_movement": (StockMovement, "inventory", stock_movement),
        "quality_test": (QualityTest, "quality", plain("quality test", lambda t: str(t))),
        "quality_audit": (QualityAudit, "quality", plain("audit", lambda a: str(a))),
        "campaign": (Campaign, "marketing", plain("campaign", lambda c: c.name)),
        "scheduled_post": (ScheduledPost, "marketing", plain("post", lambda p: str(p))),
        "shipment": (Shipment, "supply_chain", plain("shipment", lambda s: s.shipment_number)),
        "attendance_record": (AttendanceRecord, "attendance",
                              plain("attendance record", lambda r: f"{r.employee.name} {r.attendance_date:%d %b %Y}")),
        "leave_request": (LeaveRequest, "attendance",
                          plain("leave request", lambda r: f"{r.employee.name} {r.get_type_display()} {r.date:%d %b %Y}")),
        "holiday": (OfficeHoliday, "attendance", plain("holiday", lambda h: f"{h.name} {h.date:%d %b %Y}")),
    }


KINDS = None


def kinds():
    global KINDS
    if KINDS is None:
        KINDS = _models()
    return KINDS


@transaction.atomic
def delete_record(kind, pk):
    """Deletes one record of `kind`; returns (label for the audit log, module)."""
    if kind not in kinds():
        raise NotFound("Unknown record type.")
    model, module, handler = kinds()[kind]
    obj = model.objects.select_for_update(of=("self",)).filter(pk=pk).first()
    if obj is None:
        raise NotFound("This record no longer exists.")
    return handler(obj), module, str(model._meta.verbose_name)
