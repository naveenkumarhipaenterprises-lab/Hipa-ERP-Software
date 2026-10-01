from django.contrib import admin

from .models import AnalyticsRun, Conversation, Insight, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("role", "text", "attachment_name", "created_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("updated_at", "user", "title")
    inlines = [MessageInline]
    readonly_fields = ("user", "title", "created_at", "updated_at")


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    list_display = ("created_at", "module", "kind", "title")
    list_filter = ("module", "kind")
    readonly_fields = [f.name for f in Insight._meta.fields]

    def has_add_permission(self, request):
        return False  # insights come only from the analytics engine


@admin.register(AnalyticsRun)
class AnalyticsRunAdmin(admin.ModelAdmin):
    list_display = ("started_at", "finished_at")
    readonly_fields = ("started_at", "finished_at", "summary")
