"""
Report contents. Each builder returns { title, chart, breakdown, table } from real records
for one date range; chart / breakdown are None when there is nothing to draw.
Formats: 'inr' | 'number' | 'kg' | 'percent' | 'date'.
"""
from datetime import timedelta

from django.db.models import Count, F, Q, Sum

from apps.core import periods
from apps.core.metrics import num, ratio_pct
from apps.customers.models import Customer
from apps.finance.models import Transaction
from apps.inventory.models import Product
from apps.marketing.models import Campaign, MarketingMetric, Platform
from apps.production.models import ProductionBatch
from apps.quality.models import QualityTest
from apps.sales import selectors
from apps.sales.models import SalesOrder
from apps.supply_chain.models import PurchaseOrder, Shipment

# report type -> module a role must be able to read
MODULE_FOR_TYPE = {
    "sales": "sales", "inventory": "inventory", "production": "production", "marketing": "marketing",
    "customers": "customers", "supply_chain": "supply_chain", "quality": "quality", "finance": "finance",
}


def col(key, header, format=None, align=None):
    c = {"key": key, "header": header}
    if format:
        c["format"] = format
    if align or format in ("inr", "number", "kg", "percent"):
        c["align"] = align or "right"
    return c


def chart(title, kind, data, series, format=None, x_key="label"):
    if not data:
        return None
    c = {"title": title, "kind": kind, "x_key": x_key, "series": series, "data": data}
    if format:
        c["format"] = format
    return c


def breakdown(title, data, format=None):
    data = [d for d in data if d["value"]]
    if not data:
        return None
    b = {"title": title, "data": data}
    if format:
        b["format"] = format
    return b


def day_buckets(p):
    """Daily buckets for ranges up to ~31 days, weekly for longer ones, monthly for a year."""
    if p.days <= 31:
        step = 1
    elif p.days <= 120:
        step = 7
    else:
        return [(s, e, label) for s, e, label in periods.last_n_months(12, p.end) if s >= p.start.replace(day=1)]
    out, day = [], p.start
    while day <= p.end:
        last = min(day + timedelta(days=step - 1), p.end)
        out.append((day, last, day.strftime("%d %b") if step == 1 else f"{day:%d %b}–{last:%d %b}"))
        day = last + timedelta(days=1)
    return out


def sales(p):
    trend = [{"label": label, "sales": num(v)} for label, v in
             ((label, selectors.items(s, e).aggregate(t=Sum("amount"))["t"]) for s, e, label in day_buckets(p)) if v]
    orders = (SalesOrder.objects.filter(order_date__range=(p.start, p.end)).select_related("customer")
              .prefetch_related("items__product").order_by("order_date", "id"))
    return {
        "title": f"Sales Report — {p.label}",
        "chart": chart("Sales", "bar", trend, [{"key": "sales", "name": "Sales"}], "inr"),
        "breakdown": breakdown("Sales by product", [{"name": r["product__name"], "value": num(r["sales"])} for r in selectors.by_product(p.start, p.end)], "inr"),
        "table": {
            "columns": [col("order_number", "Order"), col("date", "Date", "date"), col("customer", "Customer"),
                        col("product", "Product"), col("quantity_kg", "Quantity", "kg"), col("amount", "Amount", "inr"), col("status", "Status")],
            "rows": [{"order_number": o.order_number, "date": o.order_date, "customer": o.customer.name,
                      "product": ", ".join(i.product.name for i in o.items.all()),
                      "quantity_kg": num(sum(i.quantity_kg for i in o.items.all())), "amount": num(o.total_amount),
                      "status": o.get_status_display()} for o in orders],
        },
    }


def inventory(p):
    products = list(Product.objects.filter(is_active=True))
    counts = {}
    for pr in products:
        label = Product.StockStatus(pr.stock_status).label
        counts[label] = counts.get(label, 0) + 1
    return {
        "title": f"Inventory Report — stock as of today",
        "chart": chart("Stock by product", "bar", [{"label": pr.name, "stock_kg": num(pr.stock_kg)} for pr in products],
                       [{"key": "stock_kg", "name": "Stock (kg)"}], "kg"),
        "breakdown": breakdown("Items by status", [{"name": k, "value": v} for k, v in counts.items()], "number"),
        "table": {
            "columns": [col("product", "Product"), col("stock_kg", "Stock", "kg"), col("reorder_level_kg", "Reorder level", "kg"),
                        col("price_per_kg", "Price / kg", "inr"), col("stock_value", "Stock value", "inr"), col("status", "Status")],
            "rows": [{"product": pr.name, "stock_kg": num(pr.stock_kg), "reorder_level_kg": num(pr.reorder_level_kg),
                      "price_per_kg": num(pr.price_per_kg), "stock_value": num(round(pr.stock_value, 2)),
                      "status": Product.StockStatus(pr.stock_status).label} for pr in products],
        },
    }


def production(p):
    batches = ProductionBatch.objects.select_related("product", "line").filter(start_date__range=(p.start, p.end)).order_by("start_date", "id")
    done = (ProductionBatch.objects.filter(stage=ProductionBatch.Stage.COMPLETED, completed_at__range=periods.moments(p.start, p.end))
            .values("product__name").annotate(kg=Sum("quantity_kg")).order_by("-kg"))
    return {
        "title": f"Production Report — {p.label}",
        "chart": chart("Completed output by product", "bar", [{"label": r["product__name"], "kg": num(r["kg"])} for r in done],
                       [{"key": "kg", "name": "Produced (kg)"}], "kg"),
        "breakdown": breakdown("Batches by stage", [{"name": ProductionBatch.Stage(r["stage"]).label, "value": r["n"]}
                                                    for r in batches.values("stage").annotate(n=Count("id")).order_by("-n")], "number"),
        "table": {
            "columns": [col("batch_number", "Batch"), col("product", "Product"), col("quantity_kg", "Quantity", "kg"),
                        col("line", "Line"), col("start_date", "Start", "date"), col("due_date", "Due", "date"), col("stage", "Stage")],
            "rows": [{"batch_number": b.batch_number, "product": b.product.name, "quantity_kg": num(b.quantity_kg), "line": b.line.name,
                      "start_date": b.start_date, "due_date": b.due_date, "stage": b.get_stage_display()} for b in batches],
        },
    }


def marketing(p):
    metrics = MarketingMetric.objects.filter(date__range=(p.start, p.end))
    trend = []
    for s, e, label in day_buckets(p):
        agg = metrics.filter(date__range=(s, e)).aggregate(reach=Sum("reach"), engagement=Sum("engagement"))
        if agg["reach"] or agg["engagement"]:
            trend.append({"label": label, "reach": agg["reach"] or 0, "engagement": agg["engagement"] or 0})
    campaigns = Campaign.objects.filter(start_date__lte=p.end, end_date__gte=p.start).order_by("start_date")
    today = periods.today()
    rows = []
    for c in campaigns:
        m = c.metrics.filter(date__range=(p.start, p.end)).aggregate(reach=Sum("reach"), leads=Sum("leads"), sales=Sum("sales_amount"))
        rows.append({"name": c.name, "platform": c.get_platform_display(), "start_date": c.start_date, "end_date": c.end_date,
                     "budget": num(c.budget), "reach": m["reach"] or 0, "leads": m["leads"] or 0, "sales": num(m["sales"] or 0),
                     "status": Campaign.Status(c.status_on(today)).label})
    return {
        "title": f"Marketing Report — {p.label}",
        "chart": chart("Reach and engagement", "line", trend, [{"key": "reach", "name": "Reach"}, {"key": "engagement", "name": "Engagement"}], "number"),
        "breakdown": breakdown("Engagement by platform", [{"name": Platform(r["platform"]).label, "value": r["e"]}
                                                          for r in metrics.values("platform").annotate(e=Sum("engagement")).order_by("-e")], "number"),
        "table": {
            "columns": [col("name", "Campaign"), col("platform", "Platform"), col("start_date", "Start", "date"), col("end_date", "End", "date"),
                        col("budget", "Budget", "inr"), col("reach", "Reach", "number"), col("leads", "Leads", "number"),
                        col("sales", "Sales", "inr"), col("status", "Status")],
            "rows": rows,
        },
    }


def customers(p):
    in_range = Q(orders__order_date__range=(p.start, p.end)) & ~Q(orders__status=SalesOrder.Status.CANCELLED)
    buyers = (Customer.objects.annotate(amount=Sum("orders__total_amount", filter=in_range), n=Count("orders", filter=in_range, distinct=True))
              .filter(amount__gt=0).order_by("-amount"))
    return {
        "title": f"Customer Report — {p.label}",
        "chart": chart("Top customers by purchase", "bar", [{"label": c.name, "amount": num(c.amount)} for c in buyers[:10]],
                       [{"key": "amount", "name": "Purchases"}], "inr"),
        "breakdown": breakdown("Customers by type", [{"name": Customer.Type(r["type"]).label, "value": r["n"]}
                                                     for r in Customer.objects.values("type").annotate(n=Count("id")).order_by("-n")], "number"),
        "table": {
            "columns": [col("name", "Customer"), col("type", "Type"), col("city", "City"), col("orders", "Orders", "number"),
                        col("amount", "Purchases", "inr")],
            "rows": [{"name": c.name, "type": c.get_type_display(), "city": c.city, "orders": c.n, "amount": num(c.amount)} for c in buyers],
        },
    }


def supply_chain(p):
    pos = (PurchaseOrder.objects.select_related("supplier", "material").filter(order_date__range=(p.start, p.end))
           .exclude(status=PurchaseOrder.Status.CANCELLED).order_by("order_date", "id"))
    cost = (pos.exclude(rate_per_kg=None).values("supplier__name").annotate(v=Sum(F("quantity_kg") * F("rate_per_kg"))).order_by("-v"))
    ships = Shipment.objects.filter(dispatched_on__range=(p.start, p.end))
    return {
        "title": f"Supply Chain Report — {p.label}",
        "chart": chart("Procurement cost by supplier", "bar", [{"label": r["supplier__name"], "cost": num(r["v"])} for r in cost],
                       [{"key": "cost", "name": "Cost"}], "inr"),
        "breakdown": breakdown("Shipments by status", [{"name": Shipment.Status(r["status"]).label, "value": r["n"]}
                                                       for r in ships.values("status").annotate(n=Count("id")).order_by("-n")], "number"),
        "table": {
            "columns": [col("po_number", "PO"), col("date", "Date", "date"), col("supplier", "Supplier"), col("material", "Material"),
                        col("quantity_kg", "Quantity", "kg"), col("amount", "Amount", "inr"), col("status", "Status")],
            "rows": [{"po_number": po.po_number, "date": po.order_date, "supplier": po.supplier.name, "material": po.material.name,
                      "quantity_kg": num(po.quantity_kg), "amount": num(po.amount), "status": po.get_status_display()} for po in pos],
        },
    }


def quality(p):
    tests = QualityTest.objects.select_related("batch__product").filter(test_date__range=(p.start, p.end)).order_by("test_date", "id")
    per_product = tests.values("batch__product__name").annotate(n=Count("id"), ok=Count("id", filter=Q(result=QualityTest.Result.PASS)))
    return {
        "title": f"Quality Report — {p.label}",
        "chart": chart("Pass rate by product", "bar", [{"label": r["batch__product__name"], "pass_rate": ratio_pct(r["ok"], r["n"])} for r in per_product],
                       [{"key": "pass_rate", "name": "Pass rate"}], "percent"),
        "breakdown": breakdown("Results", [{"name": QualityTest.Result(r["result"]).label, "value": r["n"]}
                                           for r in tests.values("result").annotate(n=Count("id")).order_by("-n")], "number"),
        "table": {
            "columns": [col("batch", "Batch"), col("product", "Product"), col("test_date", "Date", "date"), col("parameters", "Parameters"),
                        col("result", "Result"), col("status", "Status")],
            "rows": [{"batch": t.batch.batch_number, "product": t.batch.product.name, "test_date": t.test_date, "parameters": t.parameters,
                      "result": t.get_result_display(), "status": t.status} for t in tests],
        },
    }


def finance(p):
    tx = Transaction.objects.filter(date__range=(p.start, p.end))
    trend = []
    for s, e, label in day_buckets(p):
        part = tx.filter(date__range=(s, e))
        rev = part.filter(type="income").aggregate(t=Sum("amount"))["t"]
        exp = part.filter(type="expense").aggregate(t=Sum("amount"))["t"]
        if rev or exp:
            trend.append({"label": label, "revenue": num(rev or 0), "expenses": num(exp or 0)})
    return {
        "title": f"Finance Report — {p.label}",
        "chart": chart("Revenue and expenses", "bar", trend, [{"key": "revenue", "name": "Revenue"}, {"key": "expenses", "name": "Expenses"}], "inr"),
        "breakdown": breakdown("Expenses by category", [{"name": Transaction.category_label(r["category"]), "value": num(r["t"])}
                                                        for r in tx.filter(type="expense").values("category").annotate(t=Sum("amount")).order_by("-t")], "inr"),
        "table": {
            "columns": [col("date", "Date", "date"), col("description", "Description"), col("type", "Type"), col("category", "Category"),
                        col("amount", "Amount", "inr"), col("status", "Status")],
            "rows": [{"date": t.date, "description": t.description, "type": t.get_type_display(), "category": Transaction.category_label(t.category),
                      "amount": num(t.amount), "status": t.get_status_display()} for t in tx.order_by("date", "id")],
        },
    }


BUILDERS = {"sales": sales, "inventory": inventory, "production": production, "marketing": marketing,
            "customers": customers, "supply_chain": supply_chain, "quality": quality, "finance": finance}


def build(report_type, range_key):
    cur, _prev = periods.resolve(range_key)
    return BUILDERS[report_type](cur), cur
