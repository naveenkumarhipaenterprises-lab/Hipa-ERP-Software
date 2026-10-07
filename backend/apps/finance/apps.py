from django.apps import AppConfig


class FinanceConfig(AppConfig):
    name = "apps.finance"
    label = "finance"
    verbose_name = "Accounts"

    def ready(self):
        from .services import connect

        connect()
