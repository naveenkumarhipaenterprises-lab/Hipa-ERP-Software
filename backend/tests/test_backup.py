"""Backups: finding pg_dump, file naming, and retention that never touches files the app didn't write."""
import gzip
import os
import tempfile
import time
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from apps.system.models import BackupRun, BackupSettings
from services import backup

from .helpers import API, client_for, make_user


def touch(path, days_old=0):
    path.write_bytes(b"x")
    stamp = time.time() - days_old * 86400
    os.utime(path, (stamp, stamp))
    return path


class PgDumpLookupTests(TestCase):
    def test_finds_the_newest_windows_install_when_not_on_path(self):
        with tempfile.TemporaryDirectory() as root:
            for version in ("16", "17", "9"):
                exe = Path(root) / version / "bin" / "pg_dump.exe"
                exe.parent.mkdir(parents=True)
                exe.write_bytes(b"")
            with override_settings(PG_DUMP_PATH="no-such-pg_dump"), mock.patch.object(backup, "WINDOWS_PG_BIN", Path(root)):
                self.assertEqual(Path(backup.pg_dump_executable()), Path(root) / "17" / "bin" / "pg_dump.exe")

    def test_configured_file_wins(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as fh:
            path = fh.name
        try:
            with override_settings(PG_DUMP_PATH=path):
                self.assertEqual(backup.pg_dump_executable(), path)
        finally:
            os.unlink(path)

    def test_missing_pg_dump_is_a_recorded_failure(self):
        with tempfile.TemporaryDirectory() as root, override_settings(PG_DUMP_PATH="no-such-pg_dump", BACKUP_DIR=Path(root)), \
                mock.patch.object(backup, "WINDOWS_PG_BIN", Path(root) / "none"):
            run = backup.run_backup()
        self.assertEqual(run.status, BackupRun.Status.FAILED)
        self.assertIn("pg_dump was not found", run.error)


class BackupFileTests(TestCase):
    def test_backup_file_name_and_contents(self):
        dump = b"-- TEST dump\nCREATE TABLE public.x ();\n"
        with tempfile.TemporaryDirectory() as root, override_settings(PG_DUMP_PATH=__file__, BACKUP_DIR=Path(root)), \
                mock.patch.object(backup.subprocess, "run", return_value=mock.Mock(returncode=0, stdout=dump, stderr=b"")) as run_cmd:
            run = backup.run_backup()
            self.assertEqual(run.status, BackupRun.Status.COMPLETED, run.error)
            self.assertTrue(run.file_name.startswith("hipa_masala-supabase-") and run.file_name.endswith(".sql.gz"))
            with gzip.open(Path(root) / run.file_name) as fh:
                self.assertEqual(fh.read(), dump)
        cmd, env = run_cmd.call_args.args[0], run_cmd.call_args.kwargs["env"]
        self.assertIn("--table=public.*", cmd)
        self.assertNotIn("--schema=public", cmd)  # would add "CREATE SCHEMA public;", which breaks restores
        self.assertNotIn(env["PGPASSWORD"] or "unset", " ".join(cmd))  # password stays off the command line

    def test_failed_dump_leaves_no_file(self):
        with tempfile.TemporaryDirectory() as root, override_settings(PG_DUMP_PATH=__file__, BACKUP_DIR=Path(root)), \
                mock.patch.object(backup.subprocess, "run", return_value=mock.Mock(returncode=1, stdout=b"", stderr=b"TEST connection refused")):
            run = backup.run_backup()
            self.assertEqual((run.status, run.error), (BackupRun.Status.FAILED, "TEST connection refused"))
            self.assertEqual(list(Path(root).iterdir()), [])


class RetentionTests(TestCase):
    def test_prune_removes_only_old_app_backups(self):
        with tempfile.TemporaryDirectory() as root, override_settings(BACKUP_DIR=Path(root)):
            folder = Path(root)
            old_ours = touch(folder / "hipa_masala-supabase-20260101-020000.sql.gz", days_old=200)
            new_ours = touch(folder / "hipa_masala-supabase-20261007-020000.sql.gz")
            old_mysql = touch(folder / "hipa_masala-20260928-155514.sql.gz", days_old=200)
            snapshot = touch(folder / "source-snapshot-20261001-150332.zip", days_old=200)
            self.assertEqual(backup.prune(3), 1)
            self.assertFalse(old_ours.exists())
            for kept in (new_ours, old_mysql, snapshot):
                self.assertTrue(kept.exists(), kept.name)
            self.assertEqual(backup.prune(None), 0)  # no retention set: nothing is deleted

    def test_settings_back_up_now_uses_the_same_service(self):
        with tempfile.TemporaryDirectory() as root, override_settings(PG_DUMP_PATH="no-such-pg_dump", BACKUP_DIR=Path(root)), \
                mock.patch.object(backup, "WINDOWS_PG_BIN", Path(root) / "none"):
            res = client_for(make_user("admin")).post(f"{API}/settings/backup/run/")
        self.assertEqual(res.status_code, 500)
        self.assertIn("pg_dump was not found", res.data["detail"])
        self.assertEqual(BackupRun.objects.get().status, BackupRun.Status.FAILED)
        self.assertIsNone(BackupSettings.load().retention_months)
