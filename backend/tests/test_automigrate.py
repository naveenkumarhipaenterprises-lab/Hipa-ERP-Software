"""New migrations are applied when the server starts on Vercel, once, and a failure never stops the site."""
from unittest import mock

from django.test import TestCase, override_settings

from apps.core import automigrate


class AutoMigrateTests(TestCase):
    def run_with(self, plans, **env):
        with mock.patch.object(automigrate, "pending", side_effect=plans) as pending, \
             mock.patch.object(automigrate, "call_command") as migrate, \
             mock.patch.dict("os.environ", env, clear=False), \
             mock.patch.object(automigrate.connections["default"], "close"):
            automigrate.apply_pending_migrations()
        return pending, migrate

    @override_settings(AUTO_MIGRATE=True)
    def test_applies_waiting_migrations_once(self):
        _pending, migrate = self.run_with([["0005"], ["0005"]])
        migrate.assert_called_once_with("migrate", database="default", interactive=False, verbosity=1)

    @override_settings(AUTO_MIGRATE=True)
    def test_nothing_new_or_already_applied_by_another_process(self):
        self.assertFalse(self.run_with([[]])[1].called)
        self.assertFalse(self.run_with([["0005"], []])[1].called)

    @override_settings(AUTO_MIGRATE=False)
    def test_off(self):
        pending, migrate = self.run_with([["0005"]])
        self.assertFalse(pending.called or migrate.called)

    @override_settings(AUTO_MIGRATE=True)
    def test_never_during_the_vercel_build(self):
        pending, _migrate = self.run_with([["0005"]], VERCEL="1", CI="1")
        self.assertFalse(pending.called)

    @override_settings(AUTO_MIGRATE=True)
    def test_a_failure_is_logged_not_raised(self):
        with self.assertLogs("apps.core.automigrate", "ERROR"):
            self.run_with(RuntimeError("TEST database down"))
