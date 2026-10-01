"""Marks draft / sent quotations past their valid-until date as Expired (run daily by scripts/daily_tasks.py)."""
from django.core.management.base import BaseCommand

from apps.sales.services import expire_quotations


class Command(BaseCommand):
    help = "Mark quotations whose validity date has passed as Expired."

    def handle(self, *args, **options):
        self.stdout.write(f"expire_quotations: {expire_quotations()} quotation(s) expired")
