"""
HIPA MASALA daily jobs, run by Windows Task Scheduler with pythonw.exe (no console window):
  1. expire_quotations - quotations past their valid-until date become Expired
  2. send_due_alerts   - late supplier deliveries, supplier payments due, overdue invoices
  3. run_analytics     - insights (incl. purchase recommendations) from real data
  4. run_backup        - only if "Automatic backup" is on in Settings
Output goes to backend/logs/daily_tasks.log.
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


def main():
    (BASE_DIR / "logs").mkdir(exist_ok=True)
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
        return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
