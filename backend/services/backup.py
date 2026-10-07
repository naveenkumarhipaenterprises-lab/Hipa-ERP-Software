"""Database backups with pg_dump (Settings → Data & Backup, and the `run_backup` command)."""
import gzip
import logging
import os
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)


# Backups this app writes. Only files with this prefix are ever pruned, so other dumps kept in
# BACKUP_DIR (e.g. the old hipa_masala-<date>.sql.gz MySQL dumps) are never deleted.
FILE_PREFIX = "hipa_masala-supabase-"
WINDOWS_PG_BIN = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "PostgreSQL"


def _version(path):
    try:
        return int(path.parent.parent.name)
    except ValueError:
        return 0


def pg_dump_executable():
    """PG_DUMP_PATH if it points at a file or a command on PATH, else the newest PostgreSQL install on Windows."""
    configured = settings.PG_DUMP_PATH
    if os.path.isfile(configured):
        return configured
    found = shutil.which(configured)
    if found:
        return found
    installed = sorted(WINDOWS_PG_BIN.glob("*/bin/pg_dump.exe"), key=_version, reverse=True)
    return str(installed[0]) if installed else None


def run_backup(user=None):
    """Dumps the whole database to BACKUP_DIR as a .sql.gz file and records the run."""
    from apps.system.models import BackupRun, BackupSettings

    run = BackupRun(triggered_by=user if user and user.is_authenticated else None)
    exe = pg_dump_executable()
    db = settings.DATABASES["default"]
    if not exe:
        run.status = BackupRun.Status.FAILED
        run.error = "pg_dump was not found. Set PG_DUMP_PATH in .env to the pg_dump executable."
        run.finished_at = timezone.now()
        run.save()
        return run

    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{FILE_PREFIX}{timezone.localtime():%Y%m%d-%H%M%S}.sql.gz"
    path = settings.BACKUP_DIR / name
    # Only the app's own tables (schema "public"); Supabase manages its auth/storage schemas itself.
    # --table=public.* rather than --schema=public: the latter writes "CREATE SCHEMA public;", which fails on
    # restore because every Postgres database already has that schema. Tables, sequences, constraints,
    # indexes, row level security and data are the same either way.
    cmd = [exe, f"--host={db['HOST']}", f"--port={db['PORT']}", f"--username={db['USER']}",
           "--table=public.*", "--no-owner", "--no-privileges", "--encoding=UTF8", db["NAME"]]
    env = {**os.environ, "PGPASSWORD": db["PASSWORD"] or "",  # keeps the password off the command line
           "PGSSLMODE": db["OPTIONS"].get("sslmode", "require")}
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=1800, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="replace").strip()[:1000] or f"pg_dump exited with {proc.returncode}")
        with gzip.open(path, "wb") as fh:
            fh.write(proc.stdout)
        run.status = BackupRun.Status.COMPLETED
        run.file_name = name
        run.size_bytes = path.stat().st_size
    except Exception as exc:
        log.exception("Backup failed")
        run.status = BackupRun.Status.FAILED
        run.error = str(exc)[:1000]
        if path.exists():
            path.unlink()
    run.finished_at = timezone.now()
    run.save()
    prune(BackupSettings.load().retention_months)
    return run


def prune(retention_months):
    """
    Deletes this app's backup files older than the retention period (nothing is deleted when it isn't set).
    Only files named FILE_PREFIX… are considered; anything else in BACKUP_DIR is left alone.
    """
    if not retention_months or not settings.BACKUP_DIR.exists():
        return 0
    cutoff = timezone.now() - timedelta(days=30 * retention_months)
    removed = 0
    for file in settings.BACKUP_DIR.glob(f"{FILE_PREFIX}*.sql.gz"):
        if file.stat().st_mtime < cutoff.timestamp():
            file.unlink()
            removed += 1
    return removed
