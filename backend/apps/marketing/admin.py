from django.contrib import admin

from .models import AudienceSegment, Campaign, ContentItem, MarketingMetric, ScheduledPost


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "platform", "objective", "start_date", "end_date", "budget", "ended_on")
    list_filter = ("platform", "objective")
    search_fields = ("name",)
    readonly_fields = ("created_by", "created_at")


@admin.register(MarketingMetric)
class MarketingMetricAdmin(admin.ModelAdmin):
    """Daily numbers from each platform's analytics (reach, engagement, visitors, leads, sales)."""

    list_display = ("date", "platform", "campaign", "reach", "engagement", "website_visitors", "leads", "sales_amount")
    list_filter = ("platform", "campaign")
    date_hierarchy = "date"


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ("title", "platform", "published_on", "views", "likes", "shares")
    list_filter = ("platform",)


@admin.register(AudienceSegment)
class AudienceSegmentAdmin(admin.ModelAdmin):
    list_display = ("platform", "name", "value", "as_of")
    list_filter = ("platform", "as_of")


@admin.register(ScheduledPost)
class ScheduledPostAdmin(admin.ModelAdmin):
    list_display = ("scheduled_for", "platform", "campaign", "status")
    list_filter = ("platform", "status")
    readonly_fields = ("created_by", "created_at")
