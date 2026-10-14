"""
Marketing data entered by the team from each platform's own analytics: daily metrics (reach, engagement, website
visitors, leads, sales), content performance and audience splits. These feed the Marketing dashboard (overview,
performance, top content, audience). Adding and editing is for Marketing / Management / Super Admin; deleting goes
through the Super Admin delete (/records/marketing_metric|content_item|audience_segment/<id>/).
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core import parsing, periods
from apps.core.metrics import num, resolve_choice
from services import audit

from .models import AudienceSegment, Campaign, ContentItem, MarketingMetric, Platform
from .views import MarketingView

MAX_COUNT = 2_000_000_000  # what the database column holds


def whole(d, name, errors, label):
    """A count of 0 or more, never silently turned into 0 when it isn't a number."""
    raw = d.get(name)
    if raw in (None, ""):
        return 0
    text = str(raw).strip()
    if not text.isdigit() or int(text) > MAX_COUNT:
        errors[name] = [f"Enter the {label} as a whole number (0 or more)."]
        return 0
    return int(text)


def amount(d, name, errors, label, maximum=None):
    raw = d.get(name)
    if raw in (None, ""):
        return Decimal("0")
    try:
        value = Decimal(str(raw).strip())
        if not value.is_finite() or value < 0 or value.as_tuple().exponent < -2 or (maximum is not None and value > maximum):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        errors[name] = [f"Enter the {label} as a number of 0 or more" + (f", up to {maximum}" if maximum is not None else "")
                        + ", with at most 2 decimals."]
        return Decimal("0")
    return value


def platform(d, errors):
    try:
        value = resolve_choice(Platform, d.get("platform"), "platform")
    except ValidationError as exc:
        errors.update(exc.detail)
        return None
    if not value:
        errors["platform"] = ["Choose the platform."]
    return value


def past_date(d, name, errors, label):
    day = parsing.date(d, name, errors, label=label)
    if day and day > periods.today():
        errors[name] = [f"The {label} can't be in the future."]
    return day


def save(obj, message):
    """Saves, turning a duplicate (unique constraint) into a clear message instead of a 500."""
    try:
        with transaction.atomic():
            obj.save()
    except IntegrityError:
        raise ValidationError({"detail": message})


class DataView(MarketingView):
    """List (GET, paginated, ?search=&platform=&date_from=&date_to=) and add (POST) one kind of marketing data."""

    model = None
    date_field = None
    search_fields = ()
    what = ""

    def queryset(self):
        return self.model.objects.all()

    def get(self, request):
        qs = self.queryset()
        p = resolve_choice(Platform, self.param("platform"), "platform")
        if p:
            qs = qs.filter(platform=p)
        errors = {}
        start = parsing.date(request.query_params, "date_from", errors, required=False, label="from date")
        end = parsing.date(request.query_params, "date_to", errors, required=False, label="to date")
        if errors:
            raise ValidationError(errors)
        if start:
            qs = qs.filter(**{f"{self.date_field}__gte": start})
        if end:
            qs = qs.filter(**{f"{self.date_field}__lte": end})
        q = self.param("search")
        if q and self.search_fields:
            cond = Q()
            for f in self.search_fields:
                cond |= Q(**{f"{f}__icontains": q})
            qs = qs.filter(cond)
        return self.paginated(self.narrow(qs), self.row)

    def narrow(self, qs):
        """Extra filters of one kind of data."""
        return qs

    def post(self, request):
        obj = self.model(**self.read(request.data))
        save(obj, self.duplicate_message(obj))
        audit.record(request, f"Added {self.what}", self.label(obj))
        return Response(self.row(obj), status=status.HTTP_201_CREATED)


class DataDetailView(MarketingView):
    """PATCH: fields not sent keep their value."""

    list_view = None

    def patch(self, request, pk):
        v = self.list_view()
        v.request = request
        obj = get_object_or_404(v.queryset(), pk=pk)
        current = v.as_input(obj)
        for k, val in v.read({**current, **{k: request.data.get(k) for k in current if k in request.data}}).items():
            setattr(obj, k, val)
        save(obj, v.duplicate_message(obj))
        audit.record(request, f"Edited {v.what}", v.label(obj))
        return Response(v.row(obj))


# --- Daily metrics --------------------------------------------------------------------------------

class MetricsView(DataView):
    model = MarketingMetric
    date_field = "date"
    search_fields = ("campaign__name",)
    what = "marketing numbers"

    def queryset(self):
        return MarketingMetric.objects.select_related("campaign")

    def narrow(self, qs):
        campaign = self.int_param("campaign")
        return qs.filter(campaign_id=campaign) if campaign else qs

    def row(self, m):
        return {"id": m.id, "date": m.date, "platform": m.get_platform_display(), "platform_value": m.platform,
                "campaign": m.campaign.name if m.campaign else None, "campaign_id": m.campaign_id, "reach": m.reach,
                "engagement": m.engagement, "website_visitors": m.website_visitors, "leads": m.leads,
                "sales_amount": num(m.sales_amount)}

    def as_input(self, m):
        return {"date": m.date.isoformat(), "platform": m.platform, "campaign_id": m.campaign_id or "", "reach": m.reach,
                "engagement": m.engagement, "website_visitors": m.website_visitors, "leads": m.leads,
                "sales_amount": str(m.sales_amount)}

    def read(self, d):
        errors = {}
        day = past_date(d, "date", errors, "date")
        plat = platform(d, errors)
        campaign = parsing.record(d, "campaign_id", Campaign.objects.all(), errors, required=False, message="Choose a valid campaign.")
        counts = {f: whole(d, f, errors, label) for f, label in (("reach", "reach"), ("engagement", "engagement"),
                                                                    ("website_visitors", "website visitors"), ("leads", "leads"))}
        sales = amount(d, "sales_amount", errors, "sales amount")
        if not errors and not any(counts.values()) and not sales:
            errors["detail"] = ["Enter at least one number (reach, engagement, visitors, leads or sales)."]
        if campaign and plat and campaign.platform != plat:
            errors["campaign_id"] = [f"{campaign.name} runs on {campaign.get_platform_display()}, not this platform."]
        if errors:
            raise ValidationError(errors)
        return {"date": day, "platform": plat, "campaign": campaign, **counts, "sales_amount": sales}

    def duplicate_message(self, m):
        return (f"Numbers for {m.get_platform_display()} on {m.date:%d %b %Y}" + (f" ({m.campaign.name})" if m.campaign else "")
                + " are already entered. Edit that entry instead.")

    def label(self, m):
        return f"{m.get_platform_display()} {m.date:%d %b %Y}" + (f" ({m.campaign.name})" if m.campaign else "")


class MetricDetailView(DataDetailView):
    list_view = MetricsView


# --- Content performance ---------------------------------------------------------------------------

class ContentView(DataView):
    model = ContentItem
    date_field = "published_on"
    search_fields = ("title",)
    what = "content"

    def row(self, c):
        return {"id": c.id, "title": c.title, "platform": c.get_platform_display(), "platform_value": c.platform,
                "published_on": c.published_on, "views": c.views, "likes": c.likes, "shares": c.shares, "url": c.url or None}

    def as_input(self, c):
        return {"title": c.title, "platform": c.platform, "published_on": c.published_on.isoformat(), "views": c.views,
                "likes": c.likes, "shares": c.shares, "url": c.url}

    def read(self, d):
        errors = {}
        title = parsing.text(d, "title", 200, required=True, errors=errors, label="title")
        if len(str(d.get("title") or "").strip()) > 200:
            errors["title"] = ["The title can be at most 200 characters."]
        plat = platform(d, errors)
        published = past_date(d, "published_on", errors, "published date")
        counts = {f: whole(d, f, errors, f) for f in ("views", "likes", "shares")}
        url = str(d.get("url") or "").strip()
        if url:
            try:
                URLValidator(schemes=["http", "https"])(url)
            except DjangoValidationError:
                errors["url"] = ["Enter a full link starting with https://"]
            if len(url) > 200:
                errors["url"] = ["The link can be at most 200 characters."]
        if errors:
            raise ValidationError(errors)
        return {"title": title, "platform": plat, "published_on": published, **counts, "url": url}

    def duplicate_message(self, c):
        return "This content is already entered."

    def label(self, c):
        return f"{c.title[:80]} ({c.get_platform_display()})"


class ContentDetailView(DataDetailView):
    list_view = ContentView


# --- Audience splits ------------------------------------------------------------------------------

class SegmentsView(DataView):
    model = AudienceSegment
    date_field = "as_of"
    search_fields = ("name",)
    what = "audience figure"

    def row(self, s):
        return {"id": s.id, "platform": s.get_platform_display(), "platform_value": s.platform, "name": s.name,
                "value": num(s.value), "as_of": s.as_of}

    def as_input(self, s):
        return {"platform": s.platform, "name": s.name, "value": str(s.value), "as_of": s.as_of.isoformat()}

    def read(self, d):
        errors = {}
        plat = platform(d, errors)
        name = parsing.text(d, "name", 60, required=True, errors=errors, label="audience group")
        if len(str(d.get("name") or "").strip()) > 60:
            errors["name"] = ["The audience group can be at most 60 characters."]
        if d.get("value") in (None, ""):
            errors["value"] = ["Enter the share of the audience (%)."]
        value = amount(d, "value", errors, "share of the audience (%)", maximum=Decimal("100"))
        as_of = past_date(d, "as_of", errors, "date")
        if errors:
            raise ValidationError(errors)
        return {"platform": plat, "name": name, "value": value, "as_of": as_of}

    def duplicate_message(self, s):
        return f"{s.name} on {s.get_platform_display()} for {s.as_of:%d %b %Y} is already entered. Edit that entry instead."

    def label(self, s):
        return f"{s.get_platform_display()} {s.name} {s.as_of:%d %b %Y}"


class SegmentDetailView(DataDetailView):
    list_view = SegmentsView
