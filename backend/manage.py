#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VENV_PYTHON = BASE_DIR / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def use_project_venv():
    """
    Lets `python manage.py ...` work from any terminal: when started with a Python other
    than the project's virtual environment (backend/.venv), re-run the same command with
    the venv's Python, where the packages from requirements.txt are installed.
    """
    if not VENV_PYTHON.exists() or Path(sys.prefix).resolve() == (BASE_DIR / ".venv").resolve():
        return
    try:
        code = subprocess.call([str(VENV_PYTHON), *sys.argv])
    except KeyboardInterrupt:  # Ctrl+C also reaches the child, which shuts down on its own
        code = 0
    sys.exit(code)


def main():
    """Run administrative tasks."""
    use_project_venv()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Create the virtual environment and install the packages first:\n"
            "  py -3.14 -m venv .venv\n"
            "  .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
