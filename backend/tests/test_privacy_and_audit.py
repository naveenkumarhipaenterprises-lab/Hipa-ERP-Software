"""
Sign-in privacy and the audit trail: forgot-password never reveals whether an account exists, failed
sign-ins don't show what was typed, and password changes / resets / sign-outs are written to the audit log.
"""
from unittest import mock

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from apps.system.models import AuditLog

from .helpers import API, PASSWORD, client_for, make_user


class ForgotPasswordPrivacyTests(TestCase):
    def setUp(self):
        self.user = make_user("sales", username="ravi")
        self.client = APIClient()

    def forgot(self, email):
        return self.client.post(f"{API}/auth/password/forgot/", {"email": email}, format="json")

    def test_failed_e_mail_gives_the_same_answer_as_an_unknown_address(self):
        unknown = self.forgot("nobody@test.invalid")
        with mock.patch("apps.accounts.views.send_mail", side_effect=OSError("SMTP down")), \
                self.assertLogs("apps.accounts.views", level="ERROR"):
            known = self.forgot("ravi@test.invalid")
        self.assertEqual((known.status_code, known.data), (unknown.status_code, unknown.data))
        self.assertEqual(known.status_code, 200)

    def test_known_address_still_gets_the_e_mail(self):
        self.assertEqual(self.forgot("ravi@test.invalid").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)


class AuditTrailTests(TestCase):
    def setUp(self):
        self.user = make_user("sales", username="ravi")

    def actions(self):
        return list(AuditLog.objects.values_list("action", "target"))

    def test_password_change_is_audited(self):
        res = client_for(self.user).post(f"{API}/auth/password/change/",
                                         {"current_password": PASSWORD, "new_password": "N3w-Secure-Pass!"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertIn(("Changed own password", "ravi"), self.actions())

    def test_password_reset_is_audited(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        res = APIClient().post(f"{API}/auth/password/reset/", {"uid": uid, "token": token, "password": "N3w-Secure-Pass!"},
                               format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn(("Reset password with an e-mail link", "ravi"), self.actions())

    def test_sign_out_is_audited(self):
        self.assertEqual(client_for(self.user).post(f"{API}/auth/logout/").status_code, 204)
        entry = AuditLog.objects.get(action="Signed out (all devices)")
        self.assertEqual((entry.user, entry.target), (self.user, "ravi"))


class LoginActivityPrivacyTests(TestCase):
    def test_text_typed_for_an_unknown_account_is_not_shown(self):
        make_user("sales", username="ravi")
        APIClient().post(f"{API}/auth/login/", {"username": "Secret-Typo-123", "password": "x"}, format="json")
        APIClient().post(f"{API}/auth/login/", {"username": "ravi", "password": "wrong"}, format="json")
        rows = client_for(make_user("admin")).get(f"{API}/settings/security/login-activity/").data["results"]
        users = {r["user"] for r in rows}
        self.assertIn("Unknown account", users)
        self.assertIn("TEST sales", users)  # a known account is still named
        self.assertNotIn("Secret-Typo-123", str(rows))
