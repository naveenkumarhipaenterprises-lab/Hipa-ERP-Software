"""
Client IP handling (X-Forwarded-For can't be used to dodge rate limits or break login), rate limits on the
Django admin sign-in and AI chat, and sign-in tokens that stop working after logout / password change / reset.
"""
from unittest import mock

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import LoginActivity
from apps.accounts.views import client_ip

from .helpers import API, PASSWORD, make_user

NEW_PASSWORD = "N3w-Secure-Pass!"


class ClientIpTests(TestCase):
    def setUp(self):
        cache.clear()
        make_user("sales", username="ravi")
        self.client = APIClient()

    def login(self, password=PASSWORD, **headers):
        return self.client.post(f"{API}/auth/login/", {"username": "ravi", "password": password}, format="json", **headers)

    def test_forwarded_header_is_ignored_without_a_proxy(self):
        res = self.login(password="wrong", HTTP_X_FORWARDED_FOR="9.9.9.9")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(LoginActivity.objects.get().ip, "127.0.0.1")

    def test_long_fake_header_does_not_break_login(self):
        res = self.login(HTTP_X_FORWARDED_FOR="x" * 200)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(LoginActivity.objects.get().ip, "127.0.0.1")

    def test_changing_the_header_does_not_dodge_the_login_limit(self):
        codes = [self.login(password="wrong", HTTP_X_FORWARDED_FOR=f"10.0.0.{i}").status_code for i in range(12)]
        self.assertIn(429, codes)

    def test_behind_a_proxy_the_address_it_saw_is_used(self):
        request = RequestFactory().get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8", REMOTE_ADDR="10.0.0.1")
        with override_settings(REST_FRAMEWORK={**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}):
            self.assertEqual(client_ip(request), "5.6.7.8")  # added by our proxy; 1.2.3.4 could be faked
            request.META["HTTP_X_FORWARDED_FOR"] = "not-an-ip"
            self.assertIsNone(client_ip(request))
        self.assertEqual(client_ip(request), "10.0.0.1")


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_admin_sign_in_is_limited(self):
        codes = [self.client.post("/admin/login/", {"username": "nobody", "password": "wrong"}).status_code for _ in range(12)]
        self.assertEqual(codes[0], 200)  # the form again, with an error
        self.assertEqual(codes[-1], 429)

    def test_successful_admin_sign_in_is_not_counted(self):
        make_user("admin", username="boss", is_staff=True)
        for _ in range(12):
            res = self.client.post("/admin/login/", {"username": "boss", "password": PASSWORD})
            self.assertEqual(res.status_code, 302)
            self.client.logout()

    @mock.patch("apps.ai_assistant.views.ai_client.is_configured", return_value=False)
    def test_ai_chat_is_limited_per_user(self, _configured):
        api = APIClient()
        api.force_authenticate(make_user("admin"))
        codes = [api.post(f"{API}/ai/chat/", {"message": "hi"}, format="json").status_code for _ in range(25)]
        self.assertEqual(codes[0], 503)  # not connected (the request itself got through)
        self.assertEqual(codes[-1], 429)


class TokenRevocationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = make_user("sales", username="ravi")

    def sign_in(self):
        res = APIClient().post(f"{API}/auth/login/", {"username": "ravi", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200)
        return res.data["access"]

    def as_token(self, token):
        api = APIClient()
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return api

    def works(self, token):
        return self.as_token(token).get(f"{API}/auth/me/").status_code == 200

    def test_logout_ends_the_session_on_every_device(self):
        pc, phone = self.sign_in(), self.sign_in()
        self.assertEqual(self.as_token(pc).post(f"{API}/auth/logout/").status_code, 204)
        self.assertFalse(self.works(pc))
        self.assertFalse(self.works(phone))
        res = self.as_token(pc).get(f"{API}/auth/me/")
        self.assertEqual(res.data["detail"], "Your session has ended. Please sign in again.")
        self.assertTrue(self.works(self.sign_in()))  # signing in again works

    def test_password_change_keeps_this_device_and_ends_the_others(self):
        here, other = self.sign_in(), self.sign_in()
        res = self.as_token(here).post(f"{API}/auth/password/change/",
                                       {"current_password": PASSWORD, "new_password": NEW_PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.works(here))
        self.assertFalse(self.works(other))
        self.assertTrue(self.works(res.data["access"]))

    def test_password_reset_ends_existing_sessions(self):
        token = self.sign_in()
        self.user.refresh_from_db()  # signing in changed last_login, which reset links depend on
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        res = APIClient().post(f"{API}/auth/password/reset/", {"uid": uid, "token": default_token_generator.make_token(self.user),
                                                               "password": NEW_PASSWORD}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(self.works(token))

    def test_refresh_token_from_before_logout_gives_unusable_access(self):
        res = APIClient().post(f"{API}/auth/login/", {"username": "ravi", "password": PASSWORD}, format="json")
        refresh = res.data["refresh"]
        self.as_token(res.data["access"]).post(f"{API}/auth/logout/")
        refreshed = APIClient().post(f"{API}/auth/refresh/", {"refresh": refresh}, format="json")
        if refreshed.status_code == 200:
            self.assertFalse(self.works(refreshed.data["access"]))

    def test_tokens_issued_before_this_change_still_work_until_revoked(self):
        old = str(RefreshToken.for_user(self.user).access_token)  # no version claim
        self.assertTrue(self.works(old))
        self.user.revoke_tokens()
        self.assertFalse(self.works(old))


class SharedCacheTests(TestCase):
    """Rate-limit counters live in the database, so every server process (Vercel runs several) sees the same ones."""

    def test_counters_are_shared_between_processes(self):
        from django.core.cache.backends.db import DatabaseCache

        cache.clear()
        for _ in range(3):
            self.client.post("/admin/login/", {"username": "nobody", "password": "wrong"})
        another_process = DatabaseCache("django_cache", {})  # a fresh cache object, as in another server
        self.assertEqual(another_process.get("admin-login-failures:127.0.0.1"), 3)
