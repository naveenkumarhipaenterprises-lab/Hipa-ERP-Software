from django.core import mail
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import LoginActivity

from .helpers import API, PASSWORD, make_user


class AuthTests(TestCase):
    def setUp(self):
        cache.clear()  # login throttle counters
        self.user = make_user("sales", username="ravi")
        self.client = APIClient()

    def login(self, username="ravi", password=PASSWORD):
        return self.client.post(f"{API}/auth/login/", {"username": username, "password": password}, format="json")

    def test_login_with_username_returns_tokens_and_user(self):
        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"], {"id": self.user.id, "name": "TEST sales", "email": "ravi@test.invalid",
                                            "username": "ravi", "role": "sales", "roles": ["sales"]})
        self.assertTrue(LoginActivity.objects.filter(user=self.user, success=True).exists())

    def test_login_with_email_case_insensitive(self):
        self.assertEqual(self.login("RAVI@test.invalid").status_code, 200)

    def test_wrong_password_is_401_and_logged(self):
        res = self.login(password="wrong")
        self.assertEqual(res.status_code, 401)
        self.assertEqual(res.data["detail"], "Invalid username or password.")
        self.assertTrue(LoginActivity.objects.filter(success=False, username_attempted="ravi").exists())

    def test_unknown_user_is_401(self):
        self.assertEqual(self.login("nobody").status_code, 401)

    def test_inactive_user_gets_clear_message(self):
        self.user.is_active = False
        self.user.save()
        res = self.login()
        self.assertEqual(res.status_code, 403)
        self.assertIn("deactivated", res.data["detail"])

    def test_missing_fields_are_validation_errors(self):
        res = self.client.post(f"{API}/auth/login/", {}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("username", res.data)
        self.assertIn("password", res.data)

    def test_token_works_and_me_endpoint(self):
        token = self.login().data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        res = self.client.get(f"{API}/auth/me/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["role"], "sales")

    def test_no_token_is_401(self):
        self.assertEqual(self.client.get(f"{API}/dashboard/summary/").status_code, 401)

    def test_bad_token_is_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(self.client.get(f"{API}/auth/me/").status_code, 401)

    def test_deactivated_user_token_stops_working(self):
        token = self.login().data["access"]
        self.user.is_active = False
        self.user.save()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(self.client.get(f"{API}/auth/me/").status_code, 401)

    def test_refresh_and_logout_blacklists_refresh_token(self):
        tokens = self.login().data
        res = self.client.post(f"{API}/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(res.status_code, 200)
        new_refresh = res.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        self.assertEqual(self.client.post(f"{API}/auth/logout/", {"refresh": new_refresh}, format="json").status_code, 204)
        self.client.credentials()
        self.assertEqual(self.client.post(f"{API}/auth/refresh/", {"refresh": new_refresh}, format="json").status_code, 401)

    def test_logout_without_refresh_is_ok(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(f"{API}/auth/logout/").status_code, 204)

    def test_forgot_and_reset_password_flow(self):
        res = self.client.post(f"{API}/auth/password/forgot/", {"email": "ravi@test.invalid"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        link = next(line for line in mail.outbox[0].body.splitlines() if "reset-password?" in line)
        query = dict(p.split("=", 1) for p in link.split("?", 1)[1].split("&"))
        res = self.client.post(f"{API}/auth/password/reset/", {"uid": query["uid"], "token": query["token"], "password": "N3w-Secure-Pass!"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(self.login(password="N3w-Secure-Pass!").status_code, 200)
        # A used token no longer works
        res = self.client.post(f"{API}/auth/password/reset/", {"uid": query["uid"], "token": query["token"], "password": "An0ther-Pass!!"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_forgot_password_unknown_email_gives_same_answer(self):
        res = self.client.post(f"{API}/auth/password/forgot/", {"email": "nobody@test.invalid"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_rejects_weak_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        res = self.client.post(f"{API}/auth/password/reset/", {"uid": uid, "token": token, "password": "123"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("password", res.data)

    def test_change_password(self):
        self.client.force_authenticate(self.user)
        bad = self.client.post(f"{API}/auth/password/change/", {"current_password": "wrong", "new_password": "N3w-Secure-Pass!"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("current_password", bad.data)
        ok = self.client.post(f"{API}/auth/password/change/", {"current_password": PASSWORD, "new_password": "N3w-Secure-Pass!"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("N3w-Secure-Pass!"))

    def test_login_is_throttled(self):
        codes = [self.login(password="wrong").status_code for _ in range(12)]
        self.assertIn(429, codes)

    def test_superuser_acts_as_admin(self):
        su = make_user("sales", username="root_user", is_superuser=True, is_staff=True)
        res = self.login("root_user")
        self.assertEqual(res.data["user"]["role"], "admin")
        self.client.force_authenticate(su)
        self.assertEqual(self.client.get(f"{API}/settings/options/").status_code, 200)
