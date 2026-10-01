from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q, Sum
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.metrics import choices, kpi, num, ratio_pct, resolve_choice
from apps.core.views import ModuleAPIView
from services import audit, notifications

from .models import Budget, Transaction

T = Transaction
ZERO = Decimal("0")


def total(qs):
    return qs.aggregate(t=Sum("amount"))["t"] or ZERO


def in_period(start, end):
    return T.objects.filter(date__range=(start, end))


def display_status(t, today):
    if t.status == T.Status.PENDING and t.due_date and t.due_date < today:
        return "Overdue"
    return t.get_status_display()


def tx_row(t, today=None):
    today = today or periods.today()
    return {"id": t.id, "date": t.date, "description": t.description, "type": t.type,
            "category": T.category_label(t.category), "amount": num(t.amount), "status": display_status(t, today),
            "reference": t.reference or None}


def month_start(d):
    return date(d.year, d.month, 1)


def budget_block(today):
    b = Budget.objects.filter(month=month_start(today)).first()
    if not b:
        return None
    start, end = month_start(today), today
    return {
        "period_label": start.strftime("%B %Y"),
        "revenue": {"actual": num(total(in_period(start, end).filter(type=T.Type.INCOME))), "target": num(b.revenue_target)},
        "expenses": {"actual": num(total(in_period(start, end).filter(type=T.Type.EXPENSE))), "target": num(b.expense_limit)},
    }


def quarter_buckets(today, n=4):
    """[(start, end, 'Q3 2026')] for the last n quarters, oldest first, ending with the current one."""
    q, y, out = (today.month - 1) // 3, today.year, []
    for _ in range(n):
        start = date(y, q * 3 + 1, 1)
        next_start = date(y + 1, 1, 1) if q == 3 else date(y, q * 3 + 4, 1)
        out.append((start, min(next_start - timedelta(days=1), today), f"Q{q + 1} {y}"))
        q, y = (3, y - 1) if q == 0 else (q - 1, y)
    return out[::-1]


def breakdown(qs):
    return [{"name": T.category_label(r["category"]), "value": num(r["t"])}
            for r in qs.values("category").annotate(t=Sum("amount")).order_by("-t")]


class FinanceView(ModuleAPIView):
    module = "finance"


class OverviewView(FinanceView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        today = periods.today()

        def figures(p):
            qs = in_period(p.start, p.end)
            rev, exp = total(qs.filter(type=T.Type.INCOME)), total(qs.filter(type=T.Type.EXPENSE))
            return rev, exp, rev - exp, ratio_pct(rev - exp, rev)

        r1, e1, n1, m1 = figures(cur)
        r0, e0, n0, m0 = figures(prev)
        qs = in_period(cur.start, cur.end)
        pending = T.objects.filter(type=T.Type.EXPENSE, status=T.Status.PENDING).order_by("due_date", "date")[:8]
        return Response({
            "kpis": {"revenue": kpi(r1, r0), "expenses": kpi(e1, e0), "net_profit": kpi(n1, n0), "profit_margin_pct": kpi(m1, m0)},
            "expense_breakdown": breakdown(qs.filter(type=T.Type.EXPENSE)),
            "income_sources": breakdown(qs.filter(type=T.Type.INCOME)),
            "recent_transactions": [tx_row(t, today) for t in T.objects.all()[:6]],
            "budget": budget_block(today),
            "pending_payments": [
                {"id": t.id, "party": t.party or t.description, "kind": T.KIND_FOR_CATEGORY.get(t.category, "other"),
                 "due_date": t.due_date, "amount": num(t.amount), "status": display_status(t, today)}
                for t in pending
            ],
            "insights": insights.items_block("finance"),
        })


class RevenueExpensesView(FinanceView):
    def get(self, request):
        granularity = periods.parse_choice(self.param("granularity"), ["monthly", "quarterly"], "granularity", "monthly")
        if not T.objects.exists():
            return Response([])
        buckets = periods.last_n_months(12) if granularity == "monthly" else quarter_buckets(periods.today())
        return Response([
            {"label": label, "revenue": num(total(in_period(s, e).filter(type=T.Type.INCOME))),
             "expenses": num(total(in_period(s, e).filter(type=T.Type.EXPENSE)))}
            for s, e, label in buckets
        ])


class CashFlowView(FinanceView):
    def get(self, request):
        months = int(periods.parse_choice(self.param("months"), ["6", "3"], "months", "6"))
        done = T.objects.filter(status=T.Status.COMPLETED)
        if not done.exists():
            return Response([])
        return Response([
            {"label": label,
             "inflow": num(total(done.filter(type=T.Type.INCOME, date__range=(s, e)))),
             "outflow": num(total(done.filter(type=T.Type.EXPENSE, date__range=(s, e))))}
            for s, e, label in periods.last_n_months(months)
        ])


class OptionsView(FinanceView):
    def get(self, request):
        return Response({
            "income_categories": choices(T.IncomeCategory),
            "expense_categories": choices(T.ExpenseCategory),
            "statuses": choices(T.Status),
        })


def money(value, field, allow_zero=False):
    try:
        amount = Decimal(str(value))
        if (amount < 0 if allow_zero else amount <= 0) or amount.as_tuple().exponent < -2 or amount >= Decimal("1e12"):
            raise InvalidOperation
        return amount
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError({field: ["Enter an amount " + ("of 0 or more" if allow_zero else "greater than 0") + " (up to 2 decimals)."]})


class TransactionsView(FinanceView):
    def get(self, request):
        qs = T.objects.all()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(description__icontains=q) | Q(reference__icontains=q) | Q(party__icontains=q))
        type_ = self.param("type")
        if type_:
            if type_ not in T.Type.values:
                raise ValidationError({"type": ["Use income or expense."]})
            qs = qs.filter(type=type_)
        st = resolve_choice(T.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        today = periods.today()
        return self.paginated(qs, lambda t: tx_row(t, today))

    def post(self, request):
        d = request.data
        errors = {}
        type_ = d.get("type")
        if type_ not in T.Type.values:
            errors["type"] = ["Choose income or expense."]
        else:
            allowed = T.IncomeCategory if type_ == T.Type.INCOME else T.ExpenseCategory
            try:
                category = resolve_choice(allowed, d.get("category"), "category")
                if not category:
                    errors["category"] = ["Choose a category."]
            except ValidationError as exc:
                errors.update(exc.detail)
        description = str(d.get("description") or "").strip()
        if not description:
            errors["description"] = ["Enter a description."]
        try:
            amount = money(d.get("amount"), "amount")
        except ValidationError as exc:
            errors.update(exc.detail)
        day = parse_date(str(d.get("date") or ""))
        if not day:
            errors["date"] = ["Enter the date (YYYY-MM-DD)."]
        st = T.Status.COMPLETED
        if d.get("status"):
            try:
                st = resolve_choice(T.Status, d.get("status"), "status")
            except ValidationError as exc:
                errors.update(exc.detail)
        due = parse_date(str(d.get("due_date") or "")) if d.get("due_date") else None
        if errors:
            raise ValidationError(errors)
        t = T.objects.create(type=type_, category=category, description=description[:255], amount=amount, date=day,
                             status=st, due_date=due, party=str(d.get("party") or "").strip()[:150],
                             reference=str(d.get("reference") or "").strip()[:60], created_by=request.user)
        audit.record(request, f"Recorded {t.get_type_display().lower()}", f"₹{amount} {description[:80]}")
        if t.status == T.Status.PENDING and t.type == T.Type.EXPENSE:
            notifications.notify("payment_due", "New pending payment", f"{t.party or t.description}: ₹{amount}", type="warning", link="/finance")
        return Response(tx_row(t), status=status.HTTP_201_CREATED)


class BudgetView(FinanceView):
    def get(self, request):
        return Response(budget_block(periods.today()))

    def put(self, request):
        errors = {}
        values = {}
        for field in ("revenue_target", "expense_limit"):
            try:
                values[field] = money(request.data.get(field), field, allow_zero=True)
            except ValidationError as exc:
                errors.update(exc.detail)
        if errors:
            raise ValidationError(errors)
        today = periods.today()
        Budget.objects.update_or_create(month=month_start(today), defaults={**values, "updated_by": request.user})
        audit.record(request, "Set monthly budget", today.strftime("%B %Y"))
        return Response(budget_block(today))
