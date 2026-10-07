from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

ZERO = Decimal("0")


class Platform(models.TextChoices):
    INSTAGRAM = "instagram", "Instagram"
    FACEBOOK = "facebook", "Facebook"
    YOUTUBE = "youtube", "YouTube"
    WHATSAPP = "whatsapp", "WhatsApp"
    GOOGLE = "google", "Google Ads"
    WEBSITE = "website", "Website"
    OFFLINE = "offline", "Offline / Print"


class Campaign(models.Model):
    class Objective(models.TextChoices):
        AWARENESS = "awareness", "Brand Awareness"
        ENGAGEMENT = "engagement", "Engagement"
        LEADS = "leads", "Lead Generation"
        SALES = "sales", "Sales"
        LAUNCH = "launch", "Product Launch"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    name = models.CharField(max_length=150)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    objective = models.CharField(max_length=12, choices=Objective.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    budget = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(ZERO)])
    description = models.TextField(blank=True)
    ended_on = models.DateField(null=True, blank=True, help_text="Set when the campaign is ended early")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date", "-id"]
        constraints = [models.CheckConstraint(condition=models.Q(end_date__gte=models.F("start_date")), name="campaign_end_after_start")]

    def __str__(self):
        return self.name

    def status_on(self, day):
        if self.ended_on or day > self.end_date:
            return self.Status.COMPLETED
        if day < self.start_date:
            return self.Status.SCHEDULED
        return self.Status.ACTIVE


class MarketingMetric(models.Model):
    """
    Daily performance numbers per platform (from platform dashboards / analytics exports,
    entered in the admin or imported). Optionally tied to a campaign.
    """

    date = models.DateField(db_index=True)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.CASCADE, related_name="metrics")
    reach = models.PositiveIntegerField(default=0)
    engagement = models.PositiveIntegerField(default=0)
    website_visitors = models.PositiveIntegerField(default=0)
    leads = models.PositiveIntegerField(default=0)
    sales_amount = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO, validators=[MinValueValidator(ZERO)])

    class Meta:
        ordering = ["-date"]
        # nulls_distinct=False: also one row per day and platform when no campaign is set
        constraints = [models.UniqueConstraint(fields=["date", "platform", "campaign"], name="unique_metric_per_day",
                                               nulls_distinct=False)]

    def __str__(self):
        return f"{self.date} {self.get_platform_display()}"


class ContentItem(models.Model):
    title = models.CharField(max_length=200)
    platform = models.CharField(max_length=12, choices=Platform.choices)
    published_on = models.DateField(db_index=True)
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)
    url = models.URLField(blank=True)

    class Meta:
        ordering = ["-views"]

    def __str__(self):
        return self.title


class AudienceSegment(models.Model):
    """Audience split reported by a platform, e.g. age group 25-34 → 38 (%)."""

    platform = models.CharField(max_length=12, choices=Platform.choices)
    name = models.CharField(max_length=60)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(ZERO)])
    as_of = models.DateField()

    class Meta:
        ordering = ["platform", "name"]
        constraints = [models.UniqueConstraint(fields=["platform", "name", "as_of"], name="unique_audience_segment")]

    def __str__(self):
        return f"{self.get_platform_display()} {self.name}: {self.value}"


class ScheduledPost(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"

    platform = models.CharField(max_length=12, choices=Platform.choices)
    scheduled_for = models.DateTimeField(db_index=True)
    caption = models.TextField()
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_for"]

    def __str__(self):
        return f"{self.get_platform_display()} post {self.scheduled_for:%Y-%m-%d %H:%M}"
