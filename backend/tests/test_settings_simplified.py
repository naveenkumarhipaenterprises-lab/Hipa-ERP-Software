"""General settings: the screen sends only the company name and tagline; saved time zone / format values stay."""
from django.test import TestCase

from apps.system.models import CompanySettings

from .helpers import API, client_for, make_user


class GeneralSettingsTests(TestCase):
    def test_name_and_tagline_alone_save_and_other_values_stay(self):
        api = client_for(make_user("admin"))
        full = {"company_name": "TEST Co", "tagline": "", "timezone": "Asia/Kolkata", "date_format": "DD/MM/YYYY",
                "time_format": "12h", "currency": "INR", "language": "en"}
        first = api.put(f"{API}/settings/general/", full, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        res = api.put(f"{API}/settings/general/", {"company_name": "TEST HIPA", "tagline": "TEST Pure spices"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        s = CompanySettings.load()
        self.assertEqual((s.company_name, s.tagline, s.timezone), ("TEST HIPA", "TEST Pure spices", "Asia/Kolkata"))
        # Values that are sent are still checked
        self.assertEqual(api.put(f"{API}/settings/general/", {"company_name": "x", "timezone": "Mars/Base"}, format="json").status_code, 400)
