"""
Business rules for sales documents. Stock rules:
  - a sales order takes its goods out of stock when it is created (cancelling puts them back);
  - an invoice made from a sales order does not move stock again;
  - an invoice made without an order (directly, or from a quotation that was never ordered)
    takes its goods out when saved, and puts them back if it is cancelled;
  - a completed or pending sales return marked "restock" puts the goods back.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.core import parsing
from apps.core.money import ZERO
from apps.core.periods import today
from apps.inventory.models import Product, StockMovement
from apps.inventory.services import move_stock
from apps.system.models import BillingSettings
from services import notifications

from .models import (QuotationStatusChange, SalesInvoice, SalesInvoiceItem, SalesOrder, SalesOrderItem, SalesPayment,
                     SalesQuotation, SalesQuotationItem, SalesReturn)

QS = SalesQuotation.Status
MAX_QTY = Decimal("999999999")
MAX_PRICE = Decimal("99999999")
LINE_FIELDS = ("product", "quantity_kg", "unit_price", "discount_pct", "gst_pct")


def kg(value):
    return f"{Decimal(value).normalize():f} kg"


# --- Reading request bodies ---------------------------------------------------------------------

def read_lines(data, errors, *, default_gst=None):
    """items: [{product_id, quantity_kg, unit_price?, discount_pct?, gst_pct?}] → list of line dicts."""
    raw = data.get("items")
    if not isinstance(raw, list) or not raw:
        errors["items"] = ["Add at least one product."]
        return []
    if default_gst is None:
        default_gst = BillingSettings.load().default_sales_gst_pct
    lines, problems, seen = [], [], set()
    for n, row in enumerate(raw, start=1):
        row_errors = {}
        if not isinstance(row, dict):
            problems.append(f"Row {n}: invalid line.")
            continue
        product = parsing.record(row, "product_id", Product.objects.filter(is_active=True), row_errors, message="Choose a product.")
        qty = parsing.decimal(row, "quantity_kg", row_errors, places=3, positive=True, maximum=MAX_QTY,
                              message="Enter a quantity greater than 0.")
        price = parsing.decimal(row, "unit_price", row_errors, places=2, maximum=MAX_PRICE,
                                default=product.price_per_kg if product else None, message="Enter a unit price of 0 or more.")
        discount = parsing.decimal(row, "discount_pct", row_errors, maximum=Decimal("100"), default=ZERO,
                                   message="Enter a discount between 0 and 100%.")
        gst = parsing.decimal(row, "gst_pct", row_errors, maximum=Decimal("100"), default=default_gst or ZERO,
                              message="Enter a GST rate between 0 and 100%.")
        if product and product.pk in seen:
            row_errors["product_id"] = [f"{product.name} is already on another line."]
        if product:
            seen.add(product.pk)
        if row_errors:
            problems.append(f"Row {n}: " + " ".join(m for msgs in row_errors.values() for m in msgs))
        else:
            lines.append({"product": product, "quantity_kg": qty, "unit_price": price, "discount_pct": discount, "gst_pct": gst})
    if problems:
        errors["items"] = problems
    return lines


def read_party(data, customer, errors, *, current=None):
    """Customer details printed on the document; anything not sent is taken from the customer (or kept)."""
    defaults = {
        "customer_name": customer.name if customer else "", "company_name": "", "billing_address": customer.address if customer else "",
        "shipping_address": (customer.shipping_address or customer.address) if customer else "",
        "phone": customer.phone if customer else "", "email": customer.email if customer else "",
        "gstin": customer.gstin if customer else "",
    }
    if current:
        defaults = {k: getattr(current, k) for k in defaults}
    out = {}
    for field, max_length in (("customer_name", 150), ("company_name", 200), ("billing_address", 2000), ("shipping_address", 2000),
                              ("phone", 20), ("email", 254), ("gstin", 15)):
        out[field] = parsing.text(data, field, max_length) if field in data else defaults[field]
    out["gstin"] = out["gstin"].upper()
    if not out["customer_name"]:
        errors["customer_name"] = ["Choose a customer or enter the customer name."]
    if out["gstin"] and len(out["gstin"]) != 15:
        errors["gstin"] = ["A GSTIN has 15 characters."]
    if out["email"] and "@" not in out["email"]:
        errors["email"] = ["Enter a valid e-mail address."]
    return out


def lines_of(document):
    return [{f: getattr(i, f) for f in LINE_FIELDS} for i in document.items.select_related("product")]


def set_lines(document, item_model, parent_field, lines):
    """Replaces a document's product lines and recalculates its totals."""
    document.items.all().delete()
    for line in lines:
        item_model.objects.create(**{parent_field: document}, **line)
    document.recalculate_total()


def stock_out(lines, *, source, reference, user):
    for line in lines:
        move_stock(line["product"], "out", line["quantity_kg"], source=source, reference=reference, user=user)


def stock_in(lines, *, source, reference, user):
    for line in lines:
        move_stock(line["product"], "in", line["quantity_kg"], source=source, reference=reference, user=user)


# --- Quotations --------------------------------------------------------------------------------

def log_status(quotation, old, new, user, note=""):
    QuotationStatusChange.objects.create(quotation=quotation, from_status=old or "", to_status=new, note=note[:255],
                                         changed_by=user if user and user.is_authenticated else None)


def default_validity(quotation_date):
    days = BillingSettings.load().quotation_validity_days
    return quotation_date + timedelta(days=days) if days else None


@transaction.atomic
def change_quotation_status(quotation, new, user, note=""):
    q = SalesQuotation.objects.select_for_update().get(pk=quotation.pk)
    if new not in SalesQuotation.TRANSITIONS[q.status]:
        allowed = ", ".join(QS(s).label for s in SalesQuotation.TRANSITIONS[q.status]) or "none (it is final)"
        raise ValidationError({"status": [f"A {q.get_status_display().lower()} quotation can be moved to: {allowed}."]})
    if new in (QS.DRAFT, QS.SENT, QS.ACCEPTED) and q.valid_until < today():
        raise ValidationError({"status": ["This quotation's validity date has passed. Extend 'valid until' first."]})
    old, q.status = q.status, new
    q.save(update_fields=["status", "updated_at"])
    log_status(q, old, new, user, note)
    if new in (QS.ACCEPTED, QS.REJECTED):
        transaction.on_commit(lambda: notifications.notify(
            "quotation_updates", f"Quotation {q.quotation_number} {QS(new).label.lower()}", f"{q.customer_name}: ₹{q.grand_total:,.2f}",
            type="success" if new == QS.ACCEPTED else "warning", link="/sales?tab=quotations"))
    return q


def expire_quotations():
    """Draft or sent quotations past their valid-until date become Expired (stored, with history)."""
    count = 0
    for q in SalesQuotation.objects.filter(status__in=(QS.DRAFT, QS.SENT), valid_until__lt=today()):
        with transaction.atomic():
            locked = SalesQuotation.objects.select_for_update().get(pk=q.pk)
            if locked.status not in (QS.DRAFT, QS.SENT) or locked.valid_until >= today():
                continue
            old, locked.status = locked.status, QS.EXPIRED
            locked.save(update_fields=["status", "updated_at"])
            log_status(locked, old, QS.EXPIRED, None, "Validity date passed")
        notifications.notify("quotation_expiry", f"Quotation {q.quotation_number} expired",
                             f"{q.customer_name}: valid until {q.valid_until:%d %b %Y}.", type="warning", link="/sales?tab=quotations")
        count += 1
    return count


def check_convertible(q):
    if q.status not in SalesQuotation.CONVERTIBLE:
        raise ValidationError({"detail": f"A {q.get_status_display().lower()} quotation can't be converted."})
    if q.valid_until < today():
        raise ValidationError({"detail": "This quotation's validity date has passed. Extend 'valid until' first."})
    if not q.customer_id:
        raise ValidationError({"detail": "Link this quotation to a customer before converting it."})
    if not q.items.exists():
        raise ValidationError({"detail": "This quotation has no products."})


def mark_converted(q, user, note):
    old = q.status
    if old != QS.ACCEPTED:
        log_status(q, old, QS.ACCEPTED, user, "Accepted on conversion")
    q.status = QS.CONVERTED
    q.save(update_fields=["status", "updated_at"])
    log_status(q, QS.ACCEPTED, QS.CONVERTED, user, note)
    transaction.on_commit(lambda: notifications.notify(
        "quotation_updates", f"Quotation {q.quotation_number} converted", f"{q.customer_name}: {note}.", type="success",
        link="/sales?tab=quotations"))


# --- Orders ------------------------------------------------------------------------------------

def create_order(*, customer, order_date, lines, notes, user, quotation=None):
    order = SalesOrder.objects.create(customer=customer, order_date=order_date, notes=notes, created_by=user, quotation=quotation)
    for line in lines:
        SalesOrderItem.objects.create(order=order, **line)
    order.recalculate_total()
    stock_out(lines, source=StockMovement.Source.SALE, reference=order.order_number, user=user)
    return order


@transaction.atomic
def quotation_to_order(quotation, user, order_date=None):
    q = SalesQuotation.objects.select_for_update().get(pk=quotation.pk)
    if SalesOrder.objects.filter(quotation=q).exists():
        raise ValidationError({"detail": f"{q.quotation_number} has already been converted to sales order "
                                         f"{q.sales_order.order_number}."})
    if q.invoices.exclude(status=SalesInvoice.Status.CANCELLED).exists():
        raise ValidationError({"detail": f"{q.quotation_number} has already been invoiced directly."})
    check_convertible(q)
    order = create_order(customer=q.customer, order_date=order_date or today(), lines=lines_of(q),
                         notes=f"From quotation {q.quotation_number}", user=user, quotation=q)
    mark_converted(q, user, f"Sales order {order.order_number}")
    return order


# --- Invoices ----------------------------------------------------------------------------------

def default_due(invoice_date):
    days = BillingSettings.load().invoice_due_days
    return invoice_date + timedelta(days=days) if days is not None else None


def create_invoice(*, customer, party, invoice_date, due_date, lines, payment_terms, notes, terms, user, sales_order=None, quotation=None):
    invoice = SalesInvoice.objects.create(customer=customer, invoice_date=invoice_date, due_date=due_date, sales_order=sales_order,
                                          quotation=quotation, payment_terms=payment_terms, notes=notes, terms_conditions=terms,
                                          created_by=user, **party)
    for line in lines:
        SalesInvoiceItem.objects.create(invoice=invoice, **line)
    invoice.recalculate_total()
    if sales_order is None:
        stock_out(lines, source=StockMovement.Source.INVOICE, reference=invoice.invoice_number, user=user)
        invoice.stock_moved = True
        invoice.save(update_fields=["stock_moved"])
    return invoice


def party_from_customer(customer):
    errors = {}
    party = read_party({}, customer, errors)
    return party


def active_invoice(**lookup):
    return SalesInvoice.objects.filter(**lookup).exclude(status=SalesInvoice.Status.CANCELLED).first()


@transaction.atomic
def order_to_invoice(order, user, *, invoice_date=None, due_date=None, quotation=None):
    order = SalesOrder.objects.select_for_update().select_related("customer", "quotation").get(pk=order.pk)
    if order.status == SalesOrder.Status.CANCELLED:
        raise ValidationError({"detail": "A cancelled order can't be invoiced."})
    existing = active_invoice(sales_order=order)
    if existing:
        raise ValidationError({"detail": f"{order.order_number} is already invoiced as {existing.invoice_number}."})
    quotation = quotation or order.quotation
    source = quotation if quotation else None
    invoice_date = invoice_date or today()
    settings_ = BillingSettings.load()
    party = {f: getattr(source, f) for f in SalesQuotation.PARTY_FIELDS} if source else party_from_customer(order.customer)
    return create_invoice(
        customer=order.customer, party=party, invoice_date=invoice_date, due_date=due_date or default_due(invoice_date),
        lines=lines_of(order), payment_terms=source.payment_terms if source else settings_.invoice_payment_terms,
        notes=f"Sales order {order.order_number}", terms=settings_.invoice_terms, user=user, sales_order=order, quotation=quotation)


@transaction.atomic
def quotation_to_invoice(quotation, user, *, invoice_date=None, due_date=None):
    q = SalesQuotation.objects.select_for_update().get(pk=quotation.pk)
    existing = active_invoice(quotation=q)
    if existing:
        raise ValidationError({"detail": f"{q.quotation_number} is already invoiced as {existing.invoice_number}."})
    order = SalesOrder.objects.filter(quotation=q).first()
    if order:  # already ordered: invoice the order (its stock has already gone out)
        return order_to_invoice(order, user, invoice_date=invoice_date, due_date=due_date, quotation=q)
    check_convertible(q)
    invoice_date = invoice_date or today()
    invoice = create_invoice(
        customer=q.customer, party={f: getattr(q, f) for f in SalesQuotation.PARTY_FIELDS}, invoice_date=invoice_date,
        due_date=due_date or default_due(invoice_date), lines=lines_of(q), payment_terms=q.payment_terms,
        notes=q.notes, terms=BillingSettings.load().invoice_terms or q.terms_conditions, user=user, quotation=q)
    mark_converted(q, user, f"Sales invoice {invoice.invoice_number}")
    return invoice


@transaction.atomic
def replace_invoice_lines(invoice, lines, user):
    inv = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.sales_order_id:
        raise ValidationError({"items": ["Products on an invoice made from a sales order can't be changed."]})
    if inv.payments.filter(status=SalesPayment.Status.RECEIVED).exists() or inv.returns.exists():
        raise ValidationError({"items": ["Products can't be changed after payments or returns are recorded."]})
    if inv.stock_moved:
        stock_in(lines_of(inv), source=StockMovement.Source.INVOICE_CANCEL, reference=inv.invoice_number, user=user)
    set_lines(inv, SalesInvoiceItem, "invoice", lines)
    stock_out(lines, source=StockMovement.Source.INVOICE, reference=inv.invoice_number, user=user)
    inv.stock_moved = True
    inv.save(update_fields=["stock_moved"])
    return inv


@transaction.atomic
def cancel_invoice(invoice, user):
    inv = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status == SalesInvoice.Status.CANCELLED:
        raise ValidationError({"detail": "This invoice is already cancelled."})
    if inv.payments.filter(status=SalesPayment.Status.RECEIVED).exists():
        raise ValidationError({"detail": "Cancel the payments received on this invoice first."})
    if inv.returns.exclude(status=SalesReturn.Status.CANCELLED).exists():
        raise ValidationError({"detail": "Cancel the returns recorded on this invoice first."})
    if inv.stock_moved:
        stock_in(lines_of(inv), source=StockMovement.Source.INVOICE_CANCEL, reference=inv.invoice_number, user=user)
    inv.status = SalesInvoice.Status.CANCELLED
    inv.save(update_fields=["status", "updated_at"])
    return inv


def refresh_invoice_money(inv):
    inv.amount_paid = inv.payments.filter(status=SalesPayment.Status.RECEIVED).aggregate(t=Sum("amount"))["t"] or ZERO
    inv.credited_amount = inv.returns.filter(status=SalesReturn.Status.COMPLETED).aggregate(t=Sum("amount"))["t"] or ZERO
    inv.save(update_fields=["amount_paid", "credited_amount", "updated_at"])


# --- Payments ----------------------------------------------------------------------------------

@transaction.atomic
def receive_payment(invoice, *, amount, payment_date, method, reference, notes, user):
    inv = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status == SalesInvoice.Status.CANCELLED:
        raise ValidationError({"invoice_id": ["This invoice is cancelled."]})
    if amount > inv.balance:
        raise ValidationError({"amount": [f"Only ₹{inv.balance:,.2f} is outstanding on {inv.invoice_number}."]})
    if payment_date < inv.invoice_date:
        raise ValidationError({"payment_date": ["The payment date can't be before the invoice date."]})
    payment = SalesPayment.objects.create(invoice=inv, customer=inv.customer, amount=amount, payment_date=payment_date,
                                          payment_method=method, reference=reference, notes=notes, created_by=user)
    refresh_invoice_money(inv)
    transaction.on_commit(lambda: notifications.notify(
        "customer_payments", f"Payment received: ₹{amount:,.2f}", f"{inv.customer_name} for {inv.invoice_number}.", type="success",
        link="/sales?tab=payments"))
    return payment


@transaction.atomic
def cancel_payment(payment):
    p = SalesPayment.objects.select_for_update().get(pk=payment.pk)
    if p.status == SalesPayment.Status.CANCELLED:
        raise ValidationError({"detail": "This payment is already cancelled."})
    p.status = SalesPayment.Status.CANCELLED
    p.save(update_fields=["status", "updated_at"])
    refresh_invoice_money(SalesInvoice.objects.select_for_update().get(pk=p.invoice_id))
    return p


# --- Returns -----------------------------------------------------------------------------------

@transaction.atomic
def create_return(invoice, *, product, quantity_kg, return_date, reason, amount, restock, remarks, user):
    inv = SalesInvoice.objects.select_for_update().get(pk=invoice.pk)
    if inv.status == SalesInvoice.Status.CANCELLED:
        raise ValidationError({"invoice_id": ["This invoice is cancelled."]})
    line = inv.items.filter(product=product).first()
    if not line:
        raise ValidationError({"product_id": [f"{product.name} is not on {inv.invoice_number}."]})
    if return_date < inv.invoice_date:
        raise ValidationError({"return_date": ["The return date can't be before the invoice date."]})
    returned = (inv.returns.filter(product=product).exclude(status=SalesReturn.Status.CANCELLED)
                .aggregate(q=Sum("quantity_kg"))["q"] or ZERO)
    if quantity_kg > line.quantity_kg - returned:
        raise ValidationError({"quantity_kg": [f"Only {kg(line.quantity_kg - returned)} of {product.name} can still be returned."]})
    if amount is None:  # credit at the invoiced price, after discount, with GST
        amount = (line.total / line.quantity_kg * quantity_kg).quantize(Decimal("0.01"))
    ret = SalesReturn.objects.create(invoice=inv, customer=inv.customer, product=product, quantity_kg=quantity_kg, return_date=return_date,
                                     reason=reason, amount=amount, restock=restock, remarks=remarks, created_by=user)
    if restock:
        move_stock(product, "in", quantity_kg, source=StockMovement.Source.SALE_RETURN, reference=ret.return_number, user=user)
    return ret


@transaction.atomic
def set_return_status(ret, new_status, user):
    r = SalesReturn.objects.select_for_update().select_related("product").get(pk=ret.pk)
    if r.status != SalesReturn.Status.PENDING:
        raise ValidationError({"status": [f"A {r.get_status_display().lower()} return can't be changed."]})
    if new_status == SalesReturn.Status.CANCELLED and r.restock:
        move_stock(r.product, "out", r.quantity_kg, source=StockMovement.Source.SALE_RETURN_CANCEL, reference=r.return_number, user=user)
    r.status = new_status
    r.save(update_fields=["status", "updated_at"])
    refresh_invoice_money(SalesInvoice.objects.select_for_update().get(pk=r.invoice_id))
    return r
