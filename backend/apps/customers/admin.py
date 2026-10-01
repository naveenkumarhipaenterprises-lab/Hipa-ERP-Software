from django.contrib import admin

from .models import Customer, CustomerOffer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "type", "city", "contact_person", "phone", "status", "created_at")
    list_filter = ("type", "status", "city")
    search_fields = ("name", "city", "contact_person", "phone", "email")


@admin.register(CustomerOffer)
class CustomerOfferAdmin(admin.ModelAdmin):
    list_display = ("created_at", "segment", "channel", "recipients", "sent_by")
    readonly_fields = ("segment", "channel", "message", "recipients", "sent_by", "created_at")

    def has_add_permission(self, request):
        return False
