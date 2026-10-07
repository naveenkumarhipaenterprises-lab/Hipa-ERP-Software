"""
Company data given to the AI engine when "Use company data" is on: a compact summary of
real figures, limited to the modules the asking user's role may read.
"""
import json

from django.db.models import Count, Sum

from apps.core import periods
from apps.core.metrics import num
from apps.core.roles import can_read


def _record_models():
    """module -> models whose rows count as business data for that module."""
    from apps.customers.models import Customer
    from apps.finance.models import Transaction
    from apps.inventory.models import Product
    from apps.marketing.models import Campaign, MarketingMetric
    from apps.purchase.models import Purchase, RawMaterial, Supplier
    from apps.quality.models import QualityTest
    from apps.sales.models import SalesOrder
    from apps.supply_chain.models import Shipment

    return {
        "sales": [SalesOrder], "inventory": [Product], "customers": [Customer], "finance": [Transaction],
        "purchase": [Purchase, Supplier, RawMaterial], "quality": [QualityTest], "supply_chain": [Shipment],
        "marketing": [Campaign, MarketingMetric],
    }


def has_business_data(user):
    """True when any module this user may open has at least one real record."""
    return any(model.objects.exists() for module, models in _record_models().items() if can_read(user, module) for model in models)


def company_summary(user):
    cur, prev = periods.resolve("this_month")
    out = {"today": periods.today().isoformat(), "period": f"{cur.start} to {cur.end}", "currency": "INR"}

    if can_read(user, "sales"):
        from apps.sales import selectors

        now, before = selectors.totals(cur.start, cur.end), selectors.totals(prev.start, prev.end)
        out["sales_this_month"] = {"sales_inr": num(now["sales"]), "orders": now["orders"], "kg": num(now["kg"])}
        out["sales_previous_period"] = {"sales_inr": num(before["sales"]), "orders": before["orders"], "kg": num(before["kg"])}
        out["sales_by_product_this_month"] = [{"product": r["product__name"], "sales_inr": num(r["sales"]), "kg": num(r["kg"])}
                                              for r in selectors.by_product(cur.start, cur.end)[:15]]
        from apps.sales.models import SalesInvoice
        from apps.sales.views import quotation_summary

        out["quotations_this_month"] = quotation_summary(cur)
        issued = SalesInvoice.objects.filter(status=SalesInvoice.Status.ISSUED)
        balances = [i.balance for i in issued if i.balance > 0]
        out["invoices"] = {"issued_this_month": issued.filter(invoice_date__range=(cur.start, cur.end)).count(),
                           "unpaid_count": len(balances), "outstanding_inr": num(sum(balances)),
                           "overdue_count": sum(1 for i in issued if i.balance > 0 and i.due_date and i.due_date < periods.today())}
        out["monthly_sales_last_6_months"] =[{"month": l, "sales_inr": num(v)} for l, v in selectors.monthly_sales(periods.last_n_months(6))]
    if can_read(user, "inventory"):
        from apps.inventory.models import Product

        out["inventory"] = [{"product": p.name, "stock_kg": num(p.stock_kg), "reorder_level_kg": num(p.reorder_level_kg),
                             "status": Product.StockStatus(p.stock_status).label} for p in Product.objects.filter(is_active=True)[:40]]
    if can_read(user, "customers"):
        from apps.customers.models import Customer

        out["customers"] = {"total": Customer.objects.count(), "active": Customer.objects.filter(status="active").count()}
    if can_read(user, "finance"):
        from apps.finance.models import Transaction

        tx = Transaction.objects.counted().filter(date__range=(cur.start, cur.end))
        inc = tx.filter(type="income").aggregate(t=Sum("amount"))["t"] or 0
        exp = tx.filter(type="expense").aggregate(t=Sum("amount"))["t"] or 0
        out["finance_this_month"] = {"revenue_inr": num(inc), "expenses_inr": num(exp), "net_inr": num(inc - exp)}
    if can_read(user, "purchase"):
        from apps.purchase.models import Purchase, RawMaterial
        from apps.purchase.views import outstanding_total

        live = Purchase.objects.exclude(status=Purchase.Status.CANCELLED)
        now_p = live.filter(purchase_date__range=(cur.start, cur.end)).aggregate(n=Count("id"), v=Sum("total_amount"))
        out["purchases_this_month"] = {"purchases": now_p["n"], "value_inr": num(now_p["v"] or 0),
                                       "awaiting_receipt": live.filter(status__in=Purchase.OPEN).count(),
                                       "outstanding_supplier_payments_inr": num(outstanding_total())}
        out["raw_materials"] = [{"material": m.name, "stock": num(m.current_stock), "unit": m.unit,
                                 "reorder_level": num(m.reorder_level), "status": m.stock_status}
                                for m in RawMaterial.objects.filter(status=RawMaterial.Status.ACTIVE)[:40]]
        from apps.ai_assistant.insights import latest

        out["purchase_recommendations_from_daily_analysis"] = [{"title": i.title, "detail": i.text, "action": i.action}
                                                              for i in latest("purchase", 10)]
    if can_read(user, "quality"):
        from apps.quality.models import QualityTest

        tests = QualityTest.objects.filter(test_date__range=(cur.start, cur.end))
        out["quality_this_month"] = {"tests": tests.count(), "failed": tests.filter(result="fail").count()}
    return json.dumps(out, default=str)
