"""
HIPA MASALA daily jobs, run by Windows Task Scheduler with pythonw.exe (no console window):
  1. expire_quotations - quotations past their valid-until date become Expired
  2. send_due_alerts   - late supplier deliveries, supplier payments due, overdue invoices
  3. run_analytics     - insights (incl. purchase recommendations) from real data
  4. run_backup        - only if "Automatic backup" is on in Settings
Output goes to backend/logs/daily_tasks.log.

The task starts every hour during the working day, because this PC sleeps at night and Windows doesn't
catch up a missed run after waking from sleep. The jobs run once per day: after a successful run the date
is stored in logs/daily_tasks.last and later starts that day do nothing; after a failure the next hour retries.
"""
import io
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.chdir(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


LAST_RUN = BASE_DIR / "logs" / "daily_tasks.last"


def ran_today():
    try:
        return LAST_RUN.read_text(encoding="utf-8").strip() == f"{datetime.now():%Y-%m-%d}"
    except OSError:
        return False


def main(force=False):
    (BASE_DIR / "logs").mkdir(exist_ok=True)
    if not force and ran_today():
        return 0
    failed = run_jobs()
    if not failed:
        LAST_RUN.write_text(f"{datetime.now():%Y-%m-%d}\n", encoding="utf-8")
    return 1 if failed else 0


def run_jobs():
    with open(BASE_DIR / "logs" / "daily_tasks.log", "a", encoding="utf-8") as log:
        log.write(f"==== {datetime.now():%Y-%m-%d %H:%M:%S} ====\n")
        failed = False
        try:
            import django
            from django.core.management import call_command

            django.setup()
            for name, args in (("expire_quotations", []), ("send_due_alerts", []), ("run_analytics", []),
                               ("run_backup", ["--scheduled"])):
                out = io.StringIO()
                try:
                    call_command(name, *args, stdout=out, stderr=out)
                except Exception:
                    failed = True
                    out.write(traceback.format_exc())
                log.write(out.getvalue())
        except Exception:
            failed = True
            log.write(traceback.format_exc())
        return failed


if __name__ == "__main__":
    # --force runs the jobs even if they already ran today
    sys.exit(main(force="--force" in sys.argv))
