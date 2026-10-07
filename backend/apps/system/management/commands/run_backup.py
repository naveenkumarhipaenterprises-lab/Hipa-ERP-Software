from django.core.management.base import BaseCommand, CommandError

from apps.system.models import BackupRun, BackupSettings
from services.backup import run_backup


class Command(BaseCommand):
    help = "Backs up the database with pg_dump. Schedule it daily with --scheduled (it then runs only when automatic backup is on)."

    def add_arguments(self, parser):
        parser.add_argument("--scheduled", action="store_true", help="Skip unless automatic backup is enabled in Settings.")

    def handle(self, *args, scheduled=False, **options):
        if scheduled and not BackupSettings.load().automatic:
            self.stdout.write("Automatic backup is off; nothing to do.")
            return
        run = run_backup()
        if run.status == BackupRun.Status.FAILED:
            raise CommandError(f"Backup failed: {run.error}")
        self.stdout.write(self.style.SUCCESS(f"Backup written: {run.file_name} ({run.size_bytes} bytes)"))
