"""
Gemini integration: configuration, key handling, error messages and the "no data yet" state.
No request reaches Google here and no AI answer is faked; real calls are checked with
`manage.py check_ai` and the live API once a key is set.
"""
import inspect
from types import SimpleNamespace

from django.test import TestCase, override_settings

from apps.ai_assistant.context import company_summary, has_business_data
from apps.core.exceptions import NotConfigured
from services import ai_client

from .helpers import API, client_for, make_user

TEST_KEY = "TEST-not-a-real-key"


class GeminiConfigTests(TestCase):
    def setUp(self):
        self.user = make_user("admin")
        self.api = client_for(self.user)

    @override_settings(GEMINI_API_KEY="")
    def test_without_key_assistant_is_not_connected(self):
        self.assertFalse(self.api.get(f"{API}/ai/status/").data["available"])
        self.assertEqual(self.api.get(f"{API}/ai/home/").data["suggestions"], [])
        res = self.api.post(f"{API}/ai/chat/", {"message": "hello"}, format="json")
        self.assertEqual(res.status_code, 503)
        with self.assertRaises(NotConfigured):
            ai_client.complete("s", [{"role": "user", "content": "x"}])

    @override_settings(GEMINI_API_KEY=TEST_KEY, GEMINI_MODEL="gemini-3.8-flash")
    def test_with_key_status_reports_gemini_model_but_never_the_key(self):
        res = self.api.get(f"{API}/ai/status/")
        self.assertTrue(res.data["available"])
        self.assertEqual(res.data["models"], [{"value": "gemini-3.8-flash", "label": "gemini-3.8-flash"}])
        self.assertEqual(res.data["features"], {"web_search": False, "attachments": True})
        for path in ("/ai/status/", "/ai/home/", "/settings/integrations/"):
            self.assertNotIn(TEST_KEY, self.api.get(API + path).content.decode(), path)
        gemini = [i for i in self.api.get(f"{API}/settings/integrations/").data if i["key"] == "ai_engine"][0]
        self.assertEqual((gemini["name"], gemini["connected"]), ("Google Gemini", True))

    @override_settings(GEMINI_API_KEY=TEST_KEY)
    def test_chat_validates_before_calling_gemini(self):
        self.assertEqual(self.api.post(f"{API}/ai/chat/", {"message": "  "}, format="json").status_code, 400)
        res = self.api.post(f"{API}/ai/chat/", {"message": "hi", "search_web": True}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(self.api.post(f"{API}/ai/chat/", {"message": "hi", "conversation_id": 999}, format="json").status_code, 404)

    def test_gemini_errors_become_clear_messages(self):
        def err(code, status="", message=""):
            return SimpleNamespace(code=code, status=status, message=message)

        self.assertIsInstance(ai_client._error_for(err(429, "RESOURCE_EXHAUSTED")), ai_client.AIRateLimited)
        self.assertEqual(ai_client._error_for(err(429)).status_code, 429)
        bad_key = ai_client._error_for(err(400, "INVALID_ARGUMENT", "API key not valid. API_KEY_INVALID"))
        self.assertIn("GEMINI_API_KEY", str(bad_key.detail))
        self.assertIn("GEMINI_MODEL", str(ai_client._error_for(err(404, "NOT_FOUND")).detail))
        self.assertEqual(ai_client._error_for(err(500, "INTERNAL")).status_code, 503)
        denied = ai_client._error_for(err(403, "PERMISSION_DENIED", "Your project has been denied access. Please contact support."))
        self.assertIn("denied this API key's project", str(denied.detail))
        retired = ai_client._error_for(err(404, "NOT_FOUND", "This model models/x is no longer available to new users."))
        self.assertIn("retired", str(retired.detail))

    def test_no_anthropic_code_left(self):
        source = inspect.getsource(ai_client).lower()
        self.assertNotIn("anthropic", source)
        self.assertIn("google", source)


class BusinessDataContextTests(TestCase):
    def test_no_business_data_on_empty_database(self):
        self.assertFalse(has_business_data(make_user("admin")))

    def test_business_data_detected_per_role(self):
        from apps.inventory.models import Product

        Product.objects.create(name="TEST Turmeric", price_per_kg=250)
        self.assertTrue(has_business_data(make_user("inventory")))
        # Marketing can't open Inventory, so a product alone isn't data for them
        self.assertFalse(has_business_data(make_user("marketing")))

    def test_summary_contains_only_readable_modules(self):
        summary = company_summary(make_user("finance"))
        self.assertIn("finance_this_month", summary)
        self.assertNotIn("inventory", summary)
