"""Quotations, invoices, customer payments and sales returns (all under /api/v1/sales/)."""
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import parsing, periods
from apps.core.metrics import num, resolve_choice
from apps.core.roles import can_write
from apps.customers.models import Customer
from apps.inventory.models import Product
from apps.system.models import BillingSettings
from services import audit

from . import pdf, services
from .models import PaymentMethod, SalesInvoice, SalesPayment, SalesQuotation, SalesQuotationItem, SalesReturn
from .views import SalesView, item_row

QS = SalesQuotation.Status
IS = SalesInvoice.Status


def party(doc):
    return {f: getattr(doc, f) for f in SalesQuotation.PARTY_FIELDS}


def money(doc, total_field="grand_total"):
    return {"subtotal": num(doc.subtotal), "discount_amount": num(doc.discount_amount),
            "taxable_amount": num(doc.subtotal - doc.discount_amount), "gst_amount": num(doc.gst_amount),
            "grand_total": num(getattr(doc, total_field))}


def date_range(view, qs, field):
    if view.param("range"):
        cur, _ = periods.resolve(view.param("range"))
        qs = qs.filter(**{f"{field}__range": (cur.start, cur.end)})
    errors = {}
    start = parsing.date(view.request.query_params, "date_from", errors, required=False, label="start date")
    end = parsing.date(view.request.query_params, "date_to", errors, required=False, label="end date")
    if errors:
        raise ValidationError(errors)
    if start:
        qs = qs.filter(**{f"{field}__gte": start})
    if end:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


def pdf_response(content, filename, download):
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'{"attachment" if download else "inline"}; filename="{filename}"'
    return response


# --- Quotations --------------------------------------------------------------------------------

def quotations_qs():
    return SalesQuotation.objects.select_related("customer", "sales_order").prefetch_related("items__product", "invoices")


def quotation_row(q, editable=True):
    order = getattr(q, "sales_order", None) if hasattr(q, "sales_order") else None
    invoice = next((i for i in q.invoices.all() if i.status != IS.CANCELLED), None)
    lines = list(q.items.all())
    convertible = editable and q.status in SalesQuotation.CONVERTIBLE and q.customer_id is not None and q.valid_until >= periods.today()
    return {
        "id": q.id, "quotation_number": q.quotation_number, "quotation_date": q.quotation_date, "valid_until": q.valid_until,
        "customer_id": q.customer_id, **party(q), "products": ", ".join(i.product.name for i in lines) or None,
        **money(q), "status": q.get_status_display(), "payment_terms": q.payment_terms, "delivery_terms": q.delivery_terms,
        "notes": q.notes, "terms_conditions": q.terms_conditions,
        "sales_order_id": order.id if order else None, "sales_order_number": order.order_number if order else None,
        "invoice_id": invoice.id if invoice else None, "invoice_number": invoice.invoice_number if invoice else None,
        "can_edit": editable and q.status in (*SalesQuotation.EDITABLE, QS.EXPIRED),
        "can_delete": editable and q.status == QS.DRAFT and order is None and invoice is None,
        "can_convert_to_order": convertible and order is None and invoice is None,
        "can_convert_to_invoice": editable and invoice is None and (order is not None or convertible),
        "next_statuses": [QS(s).label for s in SalesQuotation.TRANSITIONS[q.status]] if editable else [],
    }


def quotation_detail(pk, editable):
    q = get_object_or_404(quotations_qs(), pk=pk)
    row = quotation_row(q, editable)
    row["items"] = [item_row(i) for i in q.items.all()]
    row["status_history"] = [{"from": QS(h.from_status).label if h.from_status else None, "to": QS(h.to_status).label,
                              "note": h.note or None, "changed_by": h.changed_by.name if h.changed_by else None, "changed_at": h.changed_at}
                             for h in q.status_history.select_related("changed_by")]
    return row


class QuotationsView(SalesView):
    def get(self, request):
        services.expire_quotations()
        qs = quotations_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(quotation_number__icontains=q) | Q(customer_name__icontains=q) | Q(company_name__icontains=q) |
                           Q(items__product__name__icontains=q)).distinct()
        st = resolve_choice(QS, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        customer = self.int_param("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        editable = can_write(request.user, "sales")
        return self.paginated(date_range(self, qs, "quotation_date").order_by("-quotation_date", "-id"),
                              lambda x: quotation_row(x, editable))

    def post(self, request):
        d, errors = request.data, {}
        billing = BillingSettings.load()
        customer = parsing.record(d, "customer_id", Customer.objects.filter(status=Customer.Status.ACTIVE), errors, required=False,
                                  message="Choose an active customer.")
        details = services.read_party(d, customer, errors)
        lines = services.read_lines(d, errors)
        q_date = parsing.date(d, "quotation_date", errors, required=False, label="quotation date") or periods.today()
        valid_until = parsing.date(d, "valid_until", errors, required=False, label="valid-until date") or services.default_validity(q_date)
        if "quotation_date" not in errors and q_date > periods.today():
            errors["quotation_date"] = ["The quotation date can't be in the future."]
        if not valid_until and "valid_until" not in errors:
            errors["valid_until"] = ["Enter the valid-until date (or set a default validity in Settings → Tax & Billing)."]
        elif valid_until and valid_until < max(q_date, periods.today()):
            errors["valid_until"] = ["The valid-until date can't be in the past or before the quotation date."]
        initial = str(d.get("status") or "draft").strip().lower()
        if initial not in (QS.DRAFT, QS.SENT):
            errors["status"] = ["A new quotation is Draft or Sent."]
        if errors:
            raise ValidationError(errors)
        with transaction.atomic():
            quotation = SalesQuotation.objects.create(
                customer=customer, quotation_date=q_date, valid_until=valid_until, status=initial,
                payment_terms=parsing.text(d, "payment_terms", 255) if "payment_terms" in d else billing.quotation_payment_terms,
                delivery_terms=parsing.text(d, "delivery_terms", 255) if "delivery_terms" in d else billing.quotation_delivery_terms,
                notes=parsing.text(d, "notes", 5000),
                terms_conditions=parsing.text(d, "terms_conditions", 10000) if "terms_conditions" in d else billing.quotation_terms,
                created_by=request.user, **details)
            services.set_lines(quotation, SalesQuotationItem, "quotation", lines)
            services.log_status(quotation, "", initial, request.user, "Created")
        audit.record(request, "Created quotation", quotation.quotation_number)
        return Response(quotation_detail(quotation.pk, True), status=status.HTTP_201_CREATED)


class QuotationDetailView(SalesView):
    def get(self, request, pk):
        services.expire_quotations()
        return Response(quotation_detail(pk, can_write(request.user, "sales")))

    def patch(self, request, pk):
        d, errors = request.data, {}
        with transaction.atomic():
            q = get_object_or_404(SalesQuotation.objects.select_for_update(of=("self",)), pk=pk)
            if q.status not in (*SalesQuotation.EDITABLE, QS.EXPIRED):
                raise ValidationError({"detail": f"A {q.get_status_display().lower()} quotation can't be edited."})
            customer = q.customer
            if "customer_id" in d:
                customer = parsing.record(d, "customer_id", Customer.objects.filter(status=Customer.Status.ACTIVE), errors,
                                          required=False, message="Choose an active customer.")
            details = services.read_party(d, customer, errors, current=None if "customer_id" in d else q)
            lines = services.read_lines(d, errors) if "items" in d else None
            if "quotation_date" in d:
                q.quotation_date = parsing.date(d, "quotation_date", errors, label="quotation date") or q.quotation_date
            if "valid_until" in d:
                q.valid_until = parsing.date(d, "valid_until", errors, label="valid-until date") or q.valid_until
            if q.valid_until < q.quotation_date:
                errors["valid_until"] = ["The valid-until date can't be before the quotation date."]
            for field, limit in (("payment_terms", 255), ("delivery_terms", 255), ("notes", 5000), ("terms_conditions", 10000)):
                if field in d:
                    setattr(q, field, parsing.text(d, field, limit))
            if errors:
                raise ValidationError(errors)
            q.customer = customer
            for field, value in details.items():
                setattr(q, field, value)
            if q.status == QS.EXPIRED and q.valid_until >= periods.today():
                services.log_status(q, QS.EXPIRED, QS.DRAFT, request.user, "Validity extended")
                q.status = QS.DRAFT
            q.save()
            if lines is not None:
                services.set_lines(q, SalesQuotationItem, "quotation", lines)
        audit.record(request, "Updated quotation", q.quotation_number)
        return Response(quotation_detail(pk, True))

    def delete(self, request, pk):
        q = get_object_or_404(quotations_qs(), pk=pk)
        if not quotation_row(q)["can_delete"]:
            return Response({"detail": "Only a draft quotation that was never converted can be deleted."}, status=status.HTTP_409_CONFLICT)
        number = q.quotation_number
        q.delete()
        audit.record(request, "Deleted quotation", number)
        return Response(status=status.HTTP_204_NO_CONTENT)


class QuotationStatusView(SalesView):
    def post(self, request, pk):
        errors = {}
        new = parsing.choice(request.data, "status", QS, errors, message="Choose the new status.")
        if new in (QS.CONVERTED, QS.EXPIRED):
            errors["status"] = ["Converted and Expired are set automatically."]
        if errors:
            raise ValidationError(errors)
        q = services.change_quotation_status(get_object_or_404(SalesQuotation, pk=pk), new, request.user,
                                             parsing.text(request.data, "note", 255))
        audit.record(request, f"Marked quotation {QS(new).label.lower()}", q.quotation_number)
        return Response(quotation_detail(pk, True))


class QuotationPDFView(SalesView):
    def get(self, request, pk):
        q = get_object_or_404(SalesQuotation, pk=pk)
        return pdf_response(pdf.quotation_pdf(q), f"{q.quotation_number}.pdf", self.param("download") in ("1", "true"))


class QuotationToOrderView(SalesView):
    def post(self, request, pk):
        errors = {}
        order_date = parsing.date(request.data, "order_date", errors, required=False, label="order date")
        if order_date and order_date > periods.today():
            errors["order_date"] = ["The order date can't be in the future."]
        if errors:
            raise ValidationError(errors)
        order = services.quotation_to_order(get_object_or_404(SalesQuotation, pk=pk), request.user, order_date)
        audit.record(request, "Converted quotation to sales order", order.order_number)
        from .views import order_row, orders_qs

        return Response({"quotation": quotation_detail(pk, True), "sales_order": order_row(orders_qs().get(pk=order.pk))},
                        status=status.HTTP_201_CREATED)


def read_invoice_dates(data):
    errors = {}
    invoice_date = parsing.date(data, "invoice_date", errors, required=False, label="invoice date")
    due_date = parsing.date(data, "due_date", errors, required=False, label="due date")
    if invoice_date and invoice_date > periods.today():
        errors["invoice_date"] = ["The invoice date can't be in the future."]
    if due_date and due_date < (invoice_date or periods.today()):
        errors["due_date"] = ["The due date can't be before the invoice date."]
    if errors:
        raise ValidationError(errors)
    return invoice_date, due_date


class QuotationToInvoiceView(SalesView):
    def post(self, request, pk):
        invoice_date, due_date = read_invoice_dates(request.data)
        invoice = services.quotation_to_invoice(get_object_or_404(SalesQuotation, pk=pk), request.user,
                                                invoice_date=invoice_date, due_date=due_date)
        audit.record(request, "Converted quotation to sales invoice", invoice.invoice_number)
        return Response({"quotation": quotation_detail(pk, True), "invoice": invoice_detail(invoice.pk, True)},
                        status=status.HTTP_201_CREATED)


# --- Invoices ----------------------------------------------------------------------------------

def invoices_qs():
    return SalesInvoice.objects.select_related("customer", "sales_order", "quotation").prefetch_related("items__product")


def invoice_row(inv, editable=True):
    pay = inv.payment_status
    lines = list(inv.items.all())
    return {
        "id": inv.id, "invoice_number": inv.invoice_number, "invoice_date": inv.invoice_date, "due_date": inv.due_date,
        "customer_id": inv.customer_id, **party(inv), "products": ", ".join(i.product.name for i in lines) or None, **money(inv),
        "amount_paid": num(inv.amount_paid), "credited_amount": num(inv.credited_amount), "balance": num(inv.balance),
        "status": inv.get_status_display(), "payment_status": SalesInvoice.PaymentStatus(pay).label if pay else None,
        "payment_terms": inv.payment_terms, "notes": inv.notes, "terms_conditions": inv.terms_conditions,
        "sales_order_id": inv.sales_order_id, "sales_order_number": inv.sales_order.order_number if inv.sales_order else None,
        "quotation_id": inv.quotation_id, "quotation_number": inv.quotation.quotation_number if inv.quotation else None,
        "can_edit": editable and inv.status == IS.ISSUED,
        "can_edit_items": editable and inv.status == IS.ISSUED and not inv.sales_order_id,
        "can_cancel": editable and inv.status == IS.ISSUED,
        "can_record_payment": inv.status == IS.ISSUED and inv.balance > 0,
    }


def invoice_detail(pk, editable):
    inv = get_object_or_404(invoices_qs(), pk=pk)
    row = invoice_row(inv, editable)
    row["items"] = [item_row(i) for i in inv.items.all()]
    row["payments"] = [payment_row(p, False) for p in inv.payments.select_related("invoice")]
    row["returns"] = [return_row(r, False) for r in inv.returns.select_related("invoice", "product")]
    return row


class InvoicesView(SalesView):
    def get(self, request):
        qs = invoices_qs()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(invoice_number__icontains=q) | Q(customer_name__icontains=q) | Q(company_name__icontains=q) |
                           Q(items__product__name__icontains=q)).distinct()
        st = resolve_choice(IS, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        pay = resolve_choice(SalesInvoice.PaymentStatus, self.param("payment_status"), "payment_status")
        if pay:
            from django.db.models import DecimalField, ExpressionWrapper, F

            qs = qs.filter(status=IS.ISSUED).annotate(payable_amt=ExpressionWrapper(
                F("grand_total") - F("credited_amount"), output_field=DecimalField(max_digits=14, decimal_places=2)))
            paid = Q(amount_paid__gte=F("payable_amt"))
            overdue = ~paid & Q(due_date__lt=periods.today())
            qs = qs.filter({"paid": paid, "overdue": overdue, "partially_paid": ~paid & ~overdue & Q(amount_paid__gt=0),
                            "unpaid": ~paid & ~overdue & Q(amount_paid=0)}[pay])
        customer = self.int_param("customer")
        if customer:
            qs = qs.filter(customer_id=customer)
        editable = can_write(request.user, "sales")
        return self.paginated(date_range(self, qs, "invoice_date").order_by("-invoice_date", "-id"), lambda x: invoice_row(x, editable))

    def post(self, request):
        """A direct invoice (customer + items), or `sales_order_id` to invoice an existing order."""
        d = request.data
        if d.get("sales_order_id") not in (None, ""):
            from .models import SalesOrder

            errors = {}
            order = parsing.record(d, "sales_order_id", SalesOrder.objects.all(), errors, message="Choose a sales order.")
            if errors:
                raise ValidationError(errors)
            invoice_date, due_date = read_invoice_dates(d)
            invoice = services.order_to_invoice(order, request.user, invoice_date=invoice_date, due_date=due_date)
            audit.record(request, "Created sales invoice", f"{invoice.invoice_number} from {order.order_number}")
            return Response(invoice_detail(invoice.pk, True), status=status.HTTP_201_CREATED)

        errors = {}
        billing = BillingSettings.load()
        customer = parsing.record(d, "customer_id", Customer.objects.filter(status=Customer.Status.ACTIVE), errors,
                                  message="Choose an active customer.")
        details = services.read_party(d, customer, errors)
        lines = services.read_lines(d, errors)
        try:
            invoice_date, due_date = read_invoice_dates(d)
        except ValidationError as exc:
            errors.update(exc.detail)
            invoice_date = due_date = None
        if errors:
            raise ValidationError(errors)
        invoice_date = invoice_date or periods.today()
        with transaction.atomic():
            invoice = services.create_invoice(
                customer=customer, party=details, invoice_date=invoice_date, due_date=due_date or services.default_due(invoice_date),
                lines=lines, payment_terms=parsing.text(d, "payment_terms", 255) if "payment_terms" in d else billing.invoice_payment_terms,
                notes=parsing.text(d, "notes", 5000),
                terms=parsing.text(d, "terms_conditions", 10000) if "terms_conditions" in d else billing.invoice_terms, user=request.user)
        audit.record(request, "Created sales invoice", invoice.invoice_number)
        return Response(invoice_detail(invoice.pk, True), status=status.HTTP_201_CREATED)


class InvoiceDetailView(SalesView):
    def get(self, request, pk):
        return Response(invoice_detail(pk, can_write(request.user, "sales")))

    def patch(self, request, pk):
        d, errors = request.data, {}
        inv = get_object_or_404(SalesInvoice, pk=pk)
        if inv.status == IS.CANCELLED:
            raise ValidationError({"detail": "A cancelled invoice can't be edited."})
        details = services.read_party(d, inv.customer, errors, current=inv)
        lines = services.read_lines(d, errors) if "items" in d else None
        if "due_date" in d:
            inv.due_date = parsing.date(d, "due_date", errors, required=False, label="due date")
            if inv.due_date and inv.due_date < inv.invoice_date:
                errors["due_date"] = ["The due date can't be before the invoice date."]
        for field, limit in (("payment_terms", 255), ("notes", 5000), ("terms_conditions", 10000)):
            if field in d:
                setattr(inv, field, parsing.text(d, field, limit))
        if errors:
            raise ValidationError(errors)
        with transaction.atomic():
            for field, value in details.items():
                setattr(inv, field, value)
            inv.save()
            if lines is not None:
                services.replace_invoice_lines(inv, lines, request.user)
        audit.record(request, "Updated sales invoice", inv.invoice_number)
        return Response(invoice_detail(pk, True))


class CancelInvoiceView(SalesView):
    def post(self, request, pk):
        inv = services.cancel_invoice(get_object_or_404(SalesInvoice, pk=pk), request.user)
        audit.record(request, "Cancelled sales invoice", inv.invoice_number)
        return Response(invoice_detail(pk, True))


class InvoicePDFView(SalesView):
    def get(self, request, pk):
        inv = get_object_or_404(SalesInvoice.objects.select_related("sales_order"), pk=pk)
        return pdf_response(pdf.invoice_pdf(inv), f"{inv.invoice_number}.pdf", self.param("download") in ("1", "true"))


# --- Customer payments --------------------------------------------------------------------------

def payment_row(p, editable=True):
    return {"id": p.id, "receipt_number": p.receipt_number, "invoice_id": p.invoice_id, "invoice_number": p.invoice.invoice_number,
            "customer_id": p.customer_id, "customer": p.invoice.customer_name, "amount": num(p.amount), "payment_date": p.payment_date,
            "payment_method": p.get_payment_method_display(), "reference": p.reference or None, "status": p.get_status_display(),
            "notes": p.notes or None, "can_cancel": editable and p.status == SalesPayment.Status.RECEIVED}


class PaymentsView(SalesView):
    write_module = "sales_payments"

    def get(self, request):
        qs = SalesPayment.objects.select_related("invoice")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(receipt_number__icontains=q) | Q(invoice__invoice_number__icontains=q) |
                           Q(invoice__customer_name__icontains=q) | Q(reference__icontains=q))
        st = resolve_choice(SalesPayment.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        method = resolve_choice(PaymentMethod, self.param("payment_method"), "payment_method")
        if method:
            qs = qs.filter(payment_method=method)
        for key in ("invoice", "customer"):
            value = self.int_param(key)
            if value:
                qs = qs.filter(**{f"{key}_id": value})
        editable = can_write(request.user, "sales_payments")
        return self.paginated(date_range(self, qs, "payment_date"), lambda p: payment_row(p, editable))

    def post(self, request):
        d, errors = request.data, {}
        invoice = parsing.record(d, "invoice_id", SalesInvoice.objects.filter(status=IS.ISSUED), errors, message="Choose an invoice.")
        amount = parsing.decimal(d, "amount", errors, positive=True, maximum=services.MAX_PRICE, message="Enter an amount greater than 0.")
        payment_date = parsing.date(d, "payment_date", errors, required=False, label="payment date") or periods.today()
        if payment_date > periods.today():
            errors["payment_date"] = ["The payment date can't be in the future."]
        method = parsing.choice(d, "payment_method", PaymentMethod, errors, message="Choose the payment method.")
        if errors:
            raise ValidationError(errors)
        payment = services.receive_payment(invoice, amount=amount, payment_date=payment_date, method=method,
                                           reference=parsing.text(d, "reference", 80), notes=parsing.text(d, "notes", 500),
                                           user=request.user)
        audit.record(request, "Recorded customer payment", f"{payment.receipt_number} for {invoice.invoice_number}")
        return Response(payment_row(SalesPayment.objects.select_related("invoice").get(pk=payment.pk)), status=status.HTTP_201_CREATED)


class CancelPaymentView(SalesView):
    write_module = "sales_payments"

    def post(self, request, pk):
        p = services.cancel_payment(get_object_or_404(SalesPayment, pk=pk))
        audit.record(request, "Cancelled customer payment", p.receipt_number)
        return Response(payment_row(SalesPayment.objects.select_related("invoice").get(pk=pk)))


# --- Sales returns -------------------------------------------------------------------------------

def return_row(r, editable=True):
    return {"id": r.id, "return_number": r.return_number, "invoice_id": r.invoice_id, "invoice_number": r.invoice.invoice_number,
            "customer_id": r.customer_id, "customer": r.invoice.customer_name, "product_id": r.product_id, "product": r.product.name,
            "quantity_kg": num(r.quantity_kg), "return_date": r.return_date, "reason": r.get_reason_display(), "amount": num(r.amount),
            "restock": r.restock, "status": r.get_status_display(), "remarks": r.remarks or None,
            "can_update": editable and r.status == SalesReturn.Status.PENDING}


class ReturnsView(SalesView):
    def get(self, request):
        qs = SalesReturn.objects.select_related("invoice", "product")
        q = self.param("search")
        if q:
            qs = qs.filter(Q(return_number__icontains=q) | Q(invoice__invoice_number__icontains=q) |
                           Q(invoice__customer_name__icontains=q) | Q(product__name__icontains=q))
        st = resolve_choice(SalesReturn.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        reason = resolve_choice(SalesReturn.Reason, self.param("reason"), "reason")
        if reason:
            qs = qs.filter(reason=reason)
        editable = can_write(request.user, "sales")
        return self.paginated(date_range(self, qs, "return_date"), lambda r: return_row(r, editable))

    def post(self, request):
        d, errors = request.data, {}
        invoice = parsing.record(d, "invoice_id", SalesInvoice.objects.filter(status=IS.ISSUED), errors, message="Choose an invoice.")
        product = parsing.record(d, "product_id", Product.objects.all(), errors, message="Choose a product.")
        qty = parsing.decimal(d, "quantity_kg", errors, places=3, positive=True, maximum=services.MAX_QTY,
                              message="Enter a quantity greater than 0.")
        return_date = parsing.date(d, "return_date", errors, required=False, label="return date") or periods.today()
        if return_date > periods.today():
            errors["return_date"] = ["The return date can't be in the future."]
        reason = parsing.choice(d, "reason", SalesReturn.Reason, errors, message="Choose a reason.")
        amount = parsing.decimal(d, "amount", errors, maximum=services.MAX_PRICE, required=False, message="Enter the credit amount (0 or more).")
        restock = d.get("restock", True) not in (False, "false", "0", 0, "no")
        if errors:
            raise ValidationError(errors)
        ret = services.create_return(invoice, product=product, quantity_kg=qty, return_date=return_date, reason=reason, amount=amount,
                                     restock=restock, remarks=parsing.text(d, "remarks", 500), user=request.user)
        audit.record(request, "Recorded sales return", f"{ret.return_number} on {invoice.invoice_number}")
        return Response(return_row(SalesReturn.objects.select_related("invoice", "product").get(pk=ret.pk)), status=status.HTTP_201_CREATED)


class ReturnDetailView(SalesView):
    def patch(self, request, pk):
        errors = {}
        new = parsing.choice(request.data, "status", SalesReturn.Status, errors, message="Choose Completed or Cancelled.")
        if new == SalesReturn.Status.PENDING:
            errors["status"] = ["Choose Completed or Cancelled."]
        if errors:
            raise ValidationError(errors)
        r = services.set_return_status(get_object_or_404(SalesReturn, pk=pk), new, request.user)
        audit.record(request, f"Marked sales return {SalesReturn.Status(new).label.lower()}", r.return_number)
        return Response(return_row(SalesReturn.objects.select_related("invoice", "product").get(pk=pk)))
