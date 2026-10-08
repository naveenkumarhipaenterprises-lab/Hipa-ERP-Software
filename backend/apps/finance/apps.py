from django.apps import AppConfig


class FinanceConfig(AppConfig):
    name = "apps.finance"
    label = "finance"
    # Accounts was removed from the app (replaced by Attendance). The app stays installed only so its
    # tables and their data are kept in the database; there are no endpoints, screens or posting any more.
    verbose_name = "Accounts (retired)"
