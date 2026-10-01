"""A blocked analytics library (e.g. Windows Smart App Control) must not take the rest of the API down."""
import importlib
from unittest import mock

from django.test import TestCase

from .helpers import API, client_for, make_user

real_import = importlib.import_module


def blocked(name, *args, **kwargs):
    if name.startswith("ml."):
        raise ImportError("DLL load failed while importing groupby: An Application Control policy has blocked this file.")
    return real_import(name, *args, **kwargs)


class BlockedAnalyticsTests(TestCase):
    def test_web_code_never_imports_analytics_at_module_level(self):
        from pathlib import Path

        from django.conf import settings

        for path in (Path(settings.BASE_DIR) / "apps").rglob("*.py"):
            if "management" in path.parts or "tests" in path.parts:
                continue  # commands load analytics when run; that's fine
            top_level = [line for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(("from ml", "import ml"))]
            self.assertEqual(top_level, [], f"{path} imports ml at start-up")

    def test_load_analytics_turns_a_blocked_library_into_503(self):
        from apps.core.exceptions import AnalyticsUnavailable, load_analytics

        with mock.patch("importlib.import_module", side_effect=blocked):
            with self.assertRaises(AnalyticsUnavailable):
                load_analytics("ml.forecasting", "forecast_product")

    def test_pages_work_while_analytics_is_blocked(self):
        api = client_for(make_user("admin"))
        with mock.patch("importlib.import_module", side_effect=blocked):
            for path in ("/dashboard/summary/", "/sales/overview/", "/inventory/overview/", "/purchase/overview/",
                         "/purchase/purchases/", "/supply-chain/overview/", "/quality/overview/"):
                self.assertEqual(api.get(API + path).status_code, 200, path)
