from django.apps import AppConfig


class LegacyProductionConfig(AppConfig):
    name = "apps.legacy_production"
    label = "production"
    verbose_name = "Retired production tables (migration history only)"
