"""
E-mail: customer offers report send failures clearly (and record only what was really sent),
and the mail server connection has a time limit so a stuck server can't hang a request.
"""
from unittest import mock

from django.core import mail
from django.core.mail import get_connection
from django.core.mail.backends.locmem import EmailBackend as LocMemBackend
from django.test import TestCase, override_settings

from apps.customers.models import Customer, CustomerOffer

from .helpers import API, client_for, make_user


class FailsAfterTwo(LocMemBackend):
    """Delivers two messages, then fails like a mail server that stopped accepting mail."""

    def send_messages(self, messages):
        if len(mail.outbox) >= 2:
            raise OSError("TEST mail server refused the message")
        return super().send_messages(messages)


class FailsAtOnce(LocMemBackend):
    def open(self):
        raise OSError("TEST mail server unreachable")


@mock.patch("apps.customers.views.email_channel_ready", return_value=True)
class OfferEmailTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("marketing"))
        for i in range(5):
            Customer.objects.create(name=f"TEST Customer {i}", type="retailer", city="Erode", email=f"test{i}@example.com")

    def send(self):
        return self.api.post(f"{API}/customers/offers/", {"segment": "all", "channel": "email", "message": "TEST offer"},
                             format="json")

    def test_sends_one_email_per_customer(self, _ready):
        res = self.send()
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["queued"], 5)
        self.assertEqual(len(mail.outbox), 5)
        self.assertEqual(CustomerOffer.objects.get().recipients, 5)

    @override_settings(EMAIL_BACKEND="tests.test_email.FailsAtOnce")
    def test_mail_server_down_gives_a_clear_message_and_records_nothing(self, _ready):
        res = self.send()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.data["detail"], "The offer e-mail could not be sent. Check the e-mail settings in .env.")
        self.assertFalse(CustomerOffer.objects.exists())

    @override_settings(EMAIL_BACKEND="tests.test_email.FailsAfterTwo")
    def test_partial_failure_records_only_what_was_sent(self, _ready):
        res = self.send()
        self.assertEqual(res.status_code, 503)
        self.assertIn("could not be sent to 3 of 5 customers", res.data["detail"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(CustomerOffer.objects.get().recipients, 2)


class TimeoutTests(TestCase):
    def test_smtp_connection_has_a_time_limit(self):
        conn = get_connection("django.core.mail.backends.smtp.EmailBackend")
        self.assertIsNotNone(conn.timeout)
        self.assertLessEqual(conn.timeout, 60)
