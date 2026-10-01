from django.contrib import admin

from .models import Budget, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "type", "category", "description", "amount", "status", "due_date", "party")
    list_filter = ("type", "status", "category")
    search_fields = ("description", "reference", "party")
    readonly_fields = ("created_by", "created_at")


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ("month", "revenue_target", "expense_limit", "updated_by")
    readonly_fields = ("updated_by", "updated_at")
