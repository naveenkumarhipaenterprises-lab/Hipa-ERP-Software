from django.contrib import admin

from .models import Certification, QualityAudit, QualityStandard, QualityTest


@admin.register(QualityTest)
class QualityTestAdmin(admin.ModelAdmin):
    list_display = ("test_date", "product", "material", "batch_number", "goods_receipt", "result", "tested_by")
    list_filter = ("result",)
    search_fields = ("batch_number", "product__name", "material__name", "goods_receipt__grn_number", "parameters")
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
