from django.contrib import admin

from .models import Certification, QualityAudit, QualityStandard, QualityTest


@admin.register(QualityTest)
class QualityTestAdmin(admin.ModelAdmin):
    list_display = ("test_date", "batch", "result", "tested_by")
    list_filter = ("result",)
    search_fields = ("batch__batch_number", "batch__product__name", "parameters")
    readonly_fields = ("tested_by", "created_at")


@admin.register(QualityStandard)
class QualityStandardAdmin(admin.ModelAdmin):
    list_display = ("parameter", "limit", "product")
    list_filter = ("product",)


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ("name", "detail", "valid_until")


@admin.register(QualityAudit)
class QualityAuditAdmin(admin.ModelAdmin):
    list_display = ("date", "audit_type", "auditor", "status")
    list_filter = ("audit_type", "status")
    readonly_fields = ("created_by", "created_at")
