"""
Stock and money effects of purchase records. Every change runs in one transaction with the
affected rows locked, so stock, received quantities and paid amounts never drift.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.core.periods import today
from apps.inventory.models import StockMovement
from apps.inventory.services import move_stock
from services import notifications

from .models import GoodsReceipt, MaterialMovement, Purchase, PurchaseReturn, RawMaterial, SupplierPayment

ZERO = Decimal("0")


def qty_text(value, unit):
    return f"{Decimal(value).normalize():f} {unit}"


@transaction.atomic
def move_material(material, type, quantity, *, source=MaterialMovement.Source.ADJUSTMENT, date=None, reference="", note="", user=None):
    """Records a raw-material movement and updates its current stock (row-locked)."""
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValidationError({"quantity": ["Quantity must be greater than 0."]})
    locked = RawMaterial.objects.select_for_update().get(pk=material.pk)
    was_ok = locked.stock_status == "In Stock"
    if type == MaterialMovement.Type.OUT:
        if quantity > locked.current_stock:
            raise ValidationError({"quantity": [f"Only {qty_text(locked.current_stock, locked.unit)} of {locked.name} is in stock."]})
        locked.current_stock -= quantity
    else:
        locked.current_stock += quantity
    locked.save(update_fields=["current_stock", "updated_at"])
    material.current_stock = locked.current_stock
    movement = MaterialMovement.objects.create(material=locked, type=type, source=source, quantity=quantity, date=date or today(),
                                               reference=reference[:50], note=note[:255],
                                               created_by=user if user and user.is_authenticated else None)
    if was_ok and locked.stock_status != "In Stock":
        transaction.on_commit(lambda: notifications.notify(
            "material_low_stock", f"{locked.name}: {locked.stock_status}",
            f"{qty_text(locked.current_stock, locked.unit)} left (reorder level {qty_text(locked.reorder_level, locked.unit)}).",
            type="warning" if locked.stock_status == "Reorder" else "error", link="/purchase?tab=materials"))
    return movement


def move_item(material, product, type, quantity, *, reference, note="", date=None, user=None, material_source, product_source):
    """Stock movement for whichever item a purchase is for."""
    if material:
        return move_material(material, type, quantity, source=material_source, date=date, reference=reference, note=note, user=user)
    return move_stock(product, type, quantity, source=product_source, reference=reference, note=note, user=user)


def default_due_date(supplier, purchase_date):
    return purchase_date + timedelta(days=supplier.credit_days) if supplier.credit_days is not None else None


def last_price(material=None, product=None, exclude_pk=None):
    """Unit price of the latest earlier purchase of the same item (any supplier), for price-change alerts."""
    qs = Purchase.objects.exclude(status=Purchase.Status.CANCELLED)
    qs = qs.filter(material=material) if material else qs.filter(product=product)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    prev = qs.order_by("-purchase_date", "-id").first()
    return prev.unit_price if prev else None


def notify_price_increase(purchase):
    before = last_price(purchase.material, purchase.product, exclude_pk=purchase.pk)
    if before and purchase.unit_price > before:
        change = (purchase.unit_price - before) / before * 100
        notifications.notify("purchase_price_increase", f"{purchase.item_name}: price up {change:.1f}%",
                             f"{purchase.purchase_number} from {purchase.supplier.name} at ₹{purchase.unit_price:,.2f} per {purchase.unit} "
                             f"(previously ₹{before:,.2f}).", type="warning", link="/purchase?tab=purchases")


def refresh_receipt_status(purchase):
    """Received quantity and status from the purchase's goods receipts (call with the purchase locked)."""
    accepted = purchase.goods_receipts.aggregate(q=Sum("accepted_quantity"))["q"] or ZERO
    purchase.received_quantity = accepted
    if purchase.status != Purchase.Status.CANCELLED:
        if accepted >= purchase.quantity:
            purchase.status = Purchase.Status.RECEIVED
        elif purchase.goods_receipts.exists():
            purchase.status = Purchase.Status.PARTIALLY_RECEIVED
        else:
            purchase.status = Purchase.Status.PENDING
    purchase.save(update_fields=["received_quantity", "status", "updated_at"])


def refresh_money(purchase):
    """Paid and credited (returned) amounts of a purchase (call with the purchase locked)."""
    purchase.paid_amount = purchase.payments.filter(status__in=(SupplierPayment.Status.PAID, SupplierPayment.Status.PARTIALLY_PAID)
                                                    ).aggregate(t=Sum("amount"))["t"] or ZERO
    purchase.returned_amount = purchase.returns.filter(status=PurchaseReturn.Status.COMPLETED).aggregate(t=Sum("amount"))["t"] or ZERO
    purchase.save(update_fields=["paid_amount", "returned_amount", "updated_at"])


@transaction.atomic
def receive_goods(purchase, *, received_date, received_quantity, damaged_quantity, accepted_quantity, quality_status, remarks, user):
    purchase = Purchase.objects.select_for_update().select_related("supplier", "material", "product").get(pk=purchase.pk)
    if purchase.status == Purchase.Status.CANCELLED:
        raise ValidationError({"purchase_id": ["This purchase is cancelled."]})
    if received_date < purchase.purchase_date:
        raise ValidationError({"received_date": ["The received date can't be before the purchase date."]})
    still_open = purchase.quantity - purchase.received_quantity
    if accepted_quantity > still_open:
        raise ValidationError({"accepted_quantity": [f"Only {qty_text(still_open, purchase.unit)} of this purchase is still to be received."]})
    grn = GoodsReceipt.objects.create(purchase=purchase, received_date=received_date, received_quantity=received_quantity,
                                      damaged_quantity=damaged_quantity, accepted_quantity=accepted_quantity,
                                      quality_status=quality_status, remarks=remarks, created_by=user)
    if accepted_quantity > 0:
        move_item(purchase.material, purchase.product, "in", accepted_quantity, reference=grn.grn_number, date=received_date,
                  note=f"Received from {purchase.supplier.name} ({purchase.purchase_number})", user=user,
                  material_source=MaterialMovement.Source.GOODS_RECEIPT, product_source=StockMovement.Source.PURCHASE)
        grn.stock_recorded = True
        grn.save(update_fields=["stock_recorded"])
    refresh_receipt_status(purchase)
    issues = []
    if damaged_quantity > 0:
        issues.append(f"{qty_text(damaged_quantity, purchase.unit)} damaged")
    rejected = received_quantity - damaged_quantity - accepted_quantity
    if rejected > 0:
        issues.append(f"{qty_text(rejected, purchase.unit)} not accepted")
    if quality_status == GoodsReceipt.QualityStatus.FAILED:
        issues.append("failed quality check")
    if issues:
        transaction.on_commit(lambda: notifications.notify(
            "goods_receipt_issues", f"{grn.grn_number}: {purchase.item_name}", f"{purchase.supplier.name}: {', '.join(issues)}.",
            type="warning", link="/purchase?tab=receipts"))
    return grn, purchase


@transaction.atomic
def create_return(*, purchase, supplier, material, product, quantity, unit, return_date, reason, amount, remarks, user):
    if purchase:
        purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
        already = purchase.returns.exclude(status=PurchaseReturn.Status.CANCELLED).aggregate(q=Sum("quantity"))["q"] or ZERO
        if quantity > purchase.received_quantity - already:
            left = purchase.received_quantity - already
            raise ValidationError({"quantity": [f"Only {qty_text(left, purchase.unit)} received on {purchase.purchase_number} can still be returned."]})
    ret = PurchaseReturn.objects.create(purchase=purchase, supplier=supplier, material=material, product=product, quantity=quantity,
                                        unit=unit, return_date=return_date, reason=reason, amount=amount, remarks=remarks, created_by=user)
    move_item(material, product, "out", quantity, reference=ret.return_number, date=return_date, note=f"Returned to {supplier.name}",
              user=user, material_source=MaterialMovement.Source.PURCHASE_RETURN, product_source=StockMovement.Source.PURCHASE_RETURN)
    transaction.on_commit(lambda: notifications.notify(
        "purchase_returns", f"Purchase return {ret.return_number}",
        f"{qty_text(quantity, unit)} {ret.item.name} to {supplier.name} ({ret.get_reason_display().lower()}).", link="/purchase?tab=returns"))
    return ret


@transaction.atomic
def set_return_status(ret, new_status, user):
    ret = PurchaseReturn.objects.select_for_update().select_related("supplier", "material", "product").get(pk=ret.pk)
    if ret.status != PurchaseReturn.Status.PENDING:
        raise ValidationError({"status": [f"A {ret.get_status_display().lower()} return can't be changed."]})
    if new_status == PurchaseReturn.Status.CANCELLED:
        # The goods did not leave after all: put them back into stock
        move_item(ret.material, ret.product, "in", ret.quantity, reference=ret.return_number, note="Return cancelled", user=user,
                  material_source=MaterialMovement.Source.RETURN_CANCEL, product_source=StockMovement.Source.RETURN_CANCEL)
    ret.status = new_status
    ret.save(update_fields=["status", "updated_at"])
    if ret.purchase_id:
        refresh_money(Purchase.objects.select_for_update().get(pk=ret.purchase_id))
    return ret


def payment_status_after(purchase, amount):
    """Paid if this payment settles the purchase (or has no purchase), otherwise Partially Paid."""
    if purchase is None:
        return SupplierPayment.Status.PAID
    return SupplierPayment.Status.PAID if amount >= purchase.balance else SupplierPayment.Status.PARTIALLY_PAID


@transaction.atomic
def record_payment(*, supplier, purchase, amount, payment_date, method, reference, notes, paid, user):
    if purchase:
        purchase = Purchase.objects.select_for_update().get(pk=purchase.pk)
        open_scheduled = purchase.payments.filter(status=SupplierPayment.Status.PENDING).aggregate(t=Sum("amount"))["t"] or ZERO
        if amount > purchase.balance - (ZERO if paid else open_scheduled):
            raise ValidationError({"amount": [f"Only ₹{purchase.balance - (ZERO if paid else open_scheduled):,.2f} is outstanding on "
                                              f"{purchase.purchase_number}."]})
    payment = SupplierPayment.objects.create(
        supplier=supplier, purchase=purchase, amount=amount, payment_date=payment_date, payment_method=method,
        transaction_reference=reference, notes=notes, created_by=user,
        status=payment_status_after(purchase, amount) if paid else SupplierPayment.Status.PENDING)
    if purchase:
        refresh_money(purchase)
    if not paid:
        transaction.on_commit(lambda: notifications.notify(
            "supplier_payment_due", f"Supplier payment due {payment_date:%d %b %Y}",
            f"₹{amount:,.2f} to {supplier.name}" + (f" for {purchase.purchase_number}" if purchase else "") + ".",
            type="warning", link="/purchase?tab=payments"))
    return payment


@transaction.atomic
def mark_payment_made(payment, *, payment_date, reference, user):
    payment = SupplierPayment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != SupplierPayment.Status.PENDING:
        raise ValidationError({"detail": "This payment has already been made."})
    purchase = Purchase.objects.select_for_update().get(pk=payment.purchase_id) if payment.purchase_id else None
    if purchase and payment.amount > purchase.balance:
        raise ValidationError({"amount": [f"Only ₹{purchase.balance:,.2f} is outstanding on {purchase.purchase_number}."]})
    payment.status = payment_status_after(purchase, payment.amount)
    payment.payment_date = payment_date or payment.payment_date
    if reference:
        payment.transaction_reference = reference[:80]
    payment.save(update_fields=["status", "payment_date", "transaction_reference", "updated_at"])
    if purchase:
        refresh_money(purchase)
    return payment
