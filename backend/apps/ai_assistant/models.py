from django.conf import settings
from django.db import models


class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ai_conversations")
    title = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField()
    attachment_name = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.role}: {self.text[:60]}"


class Insight(models.Model):
    """
    A finding produced by the analytics engine (ml/) from real records, e.g. a stock-out
    forecast or an unusual sales day. Written by `manage.py run_analytics`, never by hand.
    """

    class Kind(models.TextChoices):
        FORECAST = "forecast", "Forecast"
        STOCK = "stock", "Stock-out risk"
        ANOMALY = "anomaly", "Anomaly"
        SEGMENT = "segment", "Customer segment"
        QUALITY = "quality", "Quality"
        PURCHASE = "purchase", "Purchase recommendation"

    kind = models.CharField(max_length=10, choices=Kind.choices, db_index=True)
    module = models.CharField(max_length=20, db_index=True)  # which module's users may see it
    title = models.CharField(max_length=200)
    text = models.TextField()
    action = models.CharField(max_length=255, blank=True)
    data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.title


class AnalyticsRun(models.Model):
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Analytics run {self.started_at:%Y-%m-%d %H:%M}"
