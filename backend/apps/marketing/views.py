from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Max, Q, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.ai_assistant import insights
from apps.core import periods
from apps.core.metrics import choices, kpi, label_choices, num, resolve_choice
from apps.core.roles import can_write
from apps.core.views import ModuleAPIView
from services import audit

from .models import AudienceSegment, Campaign, ContentItem, MarketingMetric, Platform, ScheduledPost

CS = Campaign.Status
METRIC_FIELDS = ("reach", "engagement", "website_visitors", "leads", "sales_amount")


def sums(qs):
    agg = qs.aggregate(**{f: Sum(f) for f in METRIC_FIELDS})
    return {f: agg[f] or 0 for f in METRIC_FIELDS}


def campaign_row(c, today, editable):
    m = sums(c.metrics.all())
    st = c.status_on(today)
    return {"id": c.id, "name": c.name, "platform": c.get_platform_display(), "start_date": c.start_date, "end_date": c.end_date,
            "status": CS(st).label, "reach": m["reach"], "leads": m["leads"], "sales": num(m["sales_amount"]),
            "can_end": editable and st != CS.COMPLETED}


def post_row(p):
    return {"id": p.id, "platform": p.get_platform_display(), "scheduled_for": p.scheduled_for, "caption": p.caption,
            "campaign": p.campaign.name if p.campaign else None, "status": p.get_status_display()}


class MarketingView(ModuleAPIView):
    module = "marketing"


class OverviewView(MarketingView):
    def get(self, request):
        cur, prev = periods.resolve(self.param("range"))
        now = sums(MarketingMetric.objects.filter(date__range=(cur.start, cur.end)))
        before = sums(MarketingMetric.objects.filter(date__range=(prev.start, prev.end)))
        by_platform = list(MarketingMetric.objects.filter(date__range=(cur.start, cur.end)).values("platform")
                           .annotate(e=Sum("engagement")).filter(e__gt=0).order_by("-e"))
        total_eng = sum(r["e"] for r in by_platform)
        content = ContentItem.objects.filter(published_on__range=(cur.start, cur.end)).order_by("-views")[:5]
        return Response({
            "kpis": {
                "reach": kpi(now["reach"], before["reach"]),
                "engagement": kpi(now["engagement"], before["engagement"]),
                "website_visitors": kpi(now["website_visitors"], before["website_visitors"]),
                "marketing_sales": kpi(now["sales_amount"], before["sales_amount"]),
            },
            "channels": [{"name": Platform(r["platform"]).label, "value": round(r["e"] / total_eng * 100, 1)} for r in by_platform],
            "top_content": [{"id": c.id, "title": c.title, "platform": c.get_platform_display(), "views": c.views,
                             "likes": c.likes, "shares": c.shares, "url": c.url or None} for c in content],
            "insights": insights.block("marketing"),
        })


class PerformanceView(MarketingView):
    def get(self, request):
        days = int(periods.parse_choice(self.param("days"), ["30", "14", "7"], "days", "30"))
        end = periods.today()
        start = end - timedelta(days=days - 1)
        rows = {r["date"]: r for r in MarketingMetric.objects.filter(date__range=(start, end)).values("date")
                .annotate(reach=Sum("reach"), engagement=Sum("engagement"), website_visitors=Sum("website_visitors"))}
        if not rows:
            return Response([])
        out = []
        for i in range(days):
            day = start + timedelta(days=i)
            r = rows.get(day, {})
            out.append({"label": day.strftime("%d %b"), "reach": r.get("reach", 0), "engagement": r.get("engagement", 0),
                        "website_visitors": r.get("website_visitors", 0)})
        return Response(out)


class AudienceView(MarketingView):
    def get(self, request):
        platform = resolve_choice(Platform, self.param("platform"), "platform")
        qs = AudienceSegment.objects.all()
        if platform:
            qs = qs.filter(platform=platform)
        # Latest snapshot per platform only
        latest = dict(qs.values("platform").annotate(d=Max("as_of")).values_list("platform", "d"))
        totals = {}
        for seg in qs:
            if seg.as_of == latest.get(seg.platform):
                totals[seg.name] = totals.get(seg.name, Decimal("0")) + seg.value
        # Each platform reports percentages of its own audience: with several platforms, average them
        # (adding them up would go past 100%)
        n = len(latest) or 1
        return Response([{"name": name, "value": num((value / n).quantize(Decimal("0.01")))} for name, value in sorted(totals.items())])


class OptionsView(MarketingView):
    def get(self, request):
        return Response({"platforms": choices(Platform), "objectives": choices(Campaign.Objective), "statuses": label_choices(CS)})


class CampaignsView(MarketingView):
    def get(self, request):
        today = periods.today()
        qs = Campaign.objects.all()
        q = self.param("search")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        st = resolve_choice(CS, self.param("status"), "status")
        if st == CS.COMPLETED:
            qs = qs.filter(Q(ended_on__isnull=False) | Q(end_date__lt=today))
        elif st == CS.SCHEDULED:
            qs = qs.filter(ended_on__isnull=True, start_date__gt=today)
        elif st == CS.ACTIVE:
            qs = qs.filter(ended_on__isnull=True, start_date__lte=today, end_date__gte=today)
        editable = can_write(request.user, "marketing")
        return self.paginated(qs, lambda c: campaign_row(c, today, editable))

    def post(self, request):
        d = request.data
        errors = {}
        name = str(d.get("name") or "").strip()
        if not name:
            errors["name"] = ["Enter the campaign name."]
        for field, tc in (("platform", Platform), ("objective", Campaign.Objective)):
            try:
                if not resolve_choice(tc, d.get(field), field):
                    errors[field] = [f"Choose the {field}."]
            except ValidationError as exc:
                errors.update(exc.detail)
        start, end = parse_date(str(d.get("start_date") or "")), parse_date(str(d.get("end_date") or ""))
        if not start:
            errors["start_date"] = ["Enter the start date (YYYY-MM-DD)."]
        if not end:
            errors["end_date"] = ["Enter the end date (YYYY-MM-DD)."]
        elif start and end < start:
            errors["end_date"] = ["The end date can't be before the start date."]
        try:
            budget = Decimal(str(d.get("budget")))
            if budget < 0 or budget.as_tuple().exponent < -2:
                raise InvalidOperation
        except (InvalidOperation, ValueError, TypeError):
            errors["budget"] = ["Enter a budget of 0 or more."]
        if errors:
            raise ValidationError(errors)
        c = Campaign.objects.create(name=name[:150], platform=resolve_choice(Platform, d["platform"], "platform"),
                                    objective=resolve_choice(Campaign.Objective, d["objective"], "objective"),
                                    start_date=start, end_date=end, budget=budget,
                                    description=str(d.get("description") or "").strip(), created_by=request.user)
        audit.record(request, "Created campaign", c.name)
        return Response(campaign_row(c, periods.today(), True), status=status.HTTP_201_CREATED)


class EndCampaignView(MarketingView):
    def post(self, request, pk):
        c = get_object_or_404(Campaign, pk=pk)
        today = periods.today()
        if c.status_on(today) == CS.COMPLETED:
            raise ValidationError({"detail": "This campaign has already ended."})
        c.ended_on = today
        c.save(update_fields=["ended_on"])
        audit.record(request, "Ended campaign", c.name)
        return Response(campaign_row(c, today, True))


class PostsView(MarketingView):
    def get(self, request):
        qs = ScheduledPost.objects.select_related("campaign")
        st = resolve_choice(ScheduledPost.Status, self.param("status"), "status")
        if st:
            qs = qs.filter(status=st)
        if st == ScheduledPost.Status.SCHEDULED:
            qs = qs.filter(scheduled_for__gte=timezone.now())
        return self.paginated(qs, post_row)

    def post(self, request):
        d = request.data
        errors = {}
        try:
            platform = resolve_choice(Platform, d.get("platform"), "platform")
            if not platform:
                errors["platform"] = ["Choose the platform."]
        except ValidationError as exc:
            errors.update(exc.detail)
        when = parse_datetime(str(d.get("scheduled_for") or ""))
        if when and timezone.is_naive(when):
            when = timezone.make_aware(when)
        if not when:
            errors["scheduled_for"] = ["Enter the date and time to publish."]
        elif when <= timezone.now():
            errors["scheduled_for"] = ["Choose a time in the future."]
        caption = str(d.get("caption") or "").strip()
        if not caption:
            errors["caption"] = ["Write the post caption."]
        campaign = None
        if d.get("campaign_id") not in (None, ""):
            campaign = Campaign.objects.filter(pk=d.get("campaign_id")).first() if str(d.get("campaign_id")).isdigit() else None
            if not campaign:
                errors["campaign_id"] = ["Choose a valid campaign."]
        if errors:
            raise ValidationError(errors)
        p = ScheduledPost.objects.create(platform=platform, scheduled_for=when, caption=caption, campaign=campaign, created_by=request.user)
        audit.record(request, "Scheduled post", f"{p.get_platform_display()} {when:%d %b %Y %H:%M}")
        return Response(post_row(p), status=status.HTTP_201_CREATED)
