"""Database backups with mysqldump (Settings → Data & Backup, and the `run_backup` command)."""
import gzip
import logging
import os
import shutil
import subprocess
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)


def mysqldump_executable():
    configured = settings.MYSQLDUMP_PATH
    if os.path.isfile(configured):
        return configured
    return shutil.which(configured)


def run_backup(user=None):
    """Dumps the whole database to BACKUP_DIR as a .sql.gz file and records the run."""
    from apps.system.models import BackupRun, BackupSettings

    run = BackupRun(triggered_by=user if user and user.is_authenticated else None)
    exe = mysqldump_executable()
    db = settings.DATABASES["default"]
    if not exe:
        run.status = BackupRun.Status.FAILED
        run.error = "mysqldump was not found. Set MYSQLDUMP_PATH in .env to the mysqldump executable."
        run.finished_at = timezone.now()
        run.save()
        return run

    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{db['NAME']}-{timezone.localtime():%Y%m%d-%H%M%S}.sql.gz"
    path = settings.BACKUP_DIR / name
    cmd = [exe, f"--host={db['HOST'] or '127.0.0.1'}", f"--port={db['PORT'] or 3306}", f"--user={db['USER']}",
           "--single-transaction", "--routines", "--default-character-set=utf8mb4", db["NAME"]]
    env = {**os.environ, "MYSQL_PWD": db["PASSWORD"] or ""}  # keeps the password off the command line
    try:
        proc = subprocess.run(cmd, capture_output=True, env=env, timeout=1800, check=False)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode(errors="replace").strip()[:1000] or f"mysqldump exited with {proc.returncode}")
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
    """Deletes backup files older than the retention period (nothing is deleted when it isn't set)."""
    if not retention_months or not settings.BACKUP_DIR.exists():
        return 0
    cutoff = timezone.now() - timedelta(days=30 * retention_months)
    removed = 0
    for file in settings.BACKUP_DIR.glob("*.sql.gz"):
        if file.stat().st_mtime < cutoff.timestamp():
            file.unlink()
            removed += 1
    return removed
