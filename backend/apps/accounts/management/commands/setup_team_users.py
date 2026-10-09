"""
Load the HIPA team into the portal from a CSV file: creates or updates each login with its role and
links it to the person's Attendance employee record. Safe to run again; it only changes what differs.

    python manage.py setup_team_users team_users.csv --dry-run    # show what would change, write nothing
    python manage.py setup_team_users team_users.csv              # apply

CSV columns (header row required):
    employee_code     Attendance employee ID, e.g. 001 (optional; blank = no employee record)
    name              Full name (required)
    email             Login e-mail (required, unique)
    joining_date      DD-MM-YYYY or YYYY-MM-DD (optional)
    role              admin (Super Admin), management, sales, purchase, inventory, marketing, finance,
                      quality or supply_chain; the screen labels ("Super Admin", "Sales Team", ...) work too.
                      Several roles for one person: separate them with "+" or ";" (e.g. purchase+inventory);
                      the first is the main role, the others are extra roles (access is the union).
                      Blank = the person is skipped until a role is chosen.
    attendance_permissions   Optional, separated by ";" (e.g. check_in;check_out;leave_apply).
                      Blank = leave the person's current Attendance permissions as they are.

New users get no password: they receive the usual invitation e-mail with a link to set their own
(the same e-mail as Settings -> User Management -> Invite). Existing passwords are never touched.
Super Admins are also made Django superusers, so they can open /admin/ as well.
"""
import csv
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.models import User
from apps.attendance import permissions as attendance_perms
from apps.attendance.models import Employee
from apps.core.roles import Role
from services import audit

REQUIRED_COLUMNS = {"name", "email"}
KNOWN_COLUMNS = {"employee_code", "name", "email", "joining_date", "role", "attendance_permissions"}

# "Super Admin", "super-admin", "Sales Team", "sales" ... -> role value
ROLE_LOOKUP = {}
for _value, _label in Role.choices:
    for _key in (_value, _label, _label.removesuffix(" Team")):
        ROLE_LOOKUP[_key.lower().replace("-", " ").replace("_", " ").strip()] = _value
ROLE_LOOKUP.update({"superadmin": Role.ADMIN, "super admin": Role.ADMIN, "accounts": Role.FINANCE})


def parse_one_role(text):
    key = " ".join((text or "").strip().lower().replace("-", " ").replace("_", " ").split())
    if key not in ROLE_LOOKUP:
        raise ValueError(f"unknown role {text!r} (use one of: {', '.join(Role.values)})")
    return ROLE_LOOKUP[key]


def parse_role(text):
    """'purchase+inventory' -> ('purchase', ['inventory']); blank -> None."""
    parts = [p for p in (text or "").replace(";", "+").replace("|", "+").split("+") if p.strip()]
    if not parts:
        return None
    roles = list(dict.fromkeys(parse_one_role(p) for p in parts))
    if Role.ADMIN in roles[1:]:
        raise ValueError("Super Admin can only be the first (main) role")
    return roles[0], roles[1:]


def parse_date(text):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"joining date {text!r} must look like 31-07-2026")


def parse_permissions(text):
    text = (text or "").strip()
    if not text:
        return None
    codes = sorted({c.strip() for c in text.replace("|", ";").replace(",", ";").split(";") if c.strip()})
    unknown = [c for c in codes if c not in attendance_perms.CODES]
    if unknown:
        raise ValueError(f"unknown attendance permission(s) {', '.join(unknown)} "
                         f"(use: {', '.join(attendance_perms.CODES)})")
    return codes


def set_password_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    return f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={default_token_generator.make_token(user)}"


class Command(BaseCommand):
    help = "Create or update portal users (with roles) and their Attendance employee records from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the team CSV file (see the command's docstring for columns).")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change; write nothing, send nothing.")
        parser.add_argument("--no-invite", action="store_true",
                            help="Don't e-mail new users; print their set-password links instead.")
        parser.add_argument("--resend-invites", action="store_true",
                            help="Also re-send the invitation to listed users who haven't set a password yet.")

    # ------------------------------------------------------------------ reading
    def read_rows(self, path):
        path = Path(path)
        if not path.is_file():
            raise CommandError(f"File not found: {path}")
        with path.open(newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            headers = {h.strip().lower() for h in (reader.fieldnames or []) if h}
            missing = REQUIRED_COLUMNS - headers
            if missing:
                raise CommandError(f"The CSV is missing column(s): {', '.join(sorted(missing))}")
            unknown = headers - KNOWN_COLUMNS
            if unknown:
                raise CommandError(f"Unknown column(s): {', '.join(sorted(unknown))}. Known: {', '.join(sorted(KNOWN_COLUMNS))}")
            rows = []
            for line_no, raw in enumerate(reader, start=2):
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
                if not any(row.values()):
                    continue
                rows.append((line_no, row))
        return rows

    def validate(self, rows):
        """Returns (people, errors). Nothing is written when any row has an error."""
        people, errors = [], []
        seen_emails, seen_codes = {}, {}
        for line_no, row in rows:
            problems = []
            name = row.get("name", "")
            email = row.get("email", "").lower()
            code = row.get("employee_code", "")
            if not name:
                problems.append("name is required")
            try:
                validate_email(email)
            except ValidationError:
                problems.append(f"invalid e-mail {email!r}")
            for label, parser, key in (("role", parse_role, "role"), ("date", parse_date, "joining_date"),
                                       ("perms", parse_permissions, "attendance_permissions")):
                try:
                    row[f"_{label}"] = parser(row.get(key, ""))
                except ValueError as exc:
                    problems.append(str(exc))
            if email in seen_emails:
                problems.append(f"e-mail repeats line {seen_emails[email]}")
            if code and code.lower() in seen_codes:
                problems.append(f"employee ID {code} repeats line {seen_codes[code.lower()]}")
            seen_emails.setdefault(email, line_no)
            if code:
                seen_codes.setdefault(code.lower(), line_no)
            if problems:
                errors.append(f"line {line_no} ({name or email or '?'}): " + "; ".join(problems))
                continue
            role, extra = row["_role"] or (None, [])
            people.append({"line": line_no, "name": name, "email": email, "code": code, "joining_date": row["_date"],
                           "role": role, "extra_roles": extra, "perms": row["_perms"]})
        return people, errors

    # ------------------------------------------------------------------ writing
    def handle(self, *args, csv_path, dry_run, no_invite, resend_invites, **options):
        people, errors = self.validate(self.read_rows(csv_path))
        if errors:
            raise CommandError("Nothing was changed. Fix these rows first:\n  " + "\n  ".join(errors))

        self.invites = []  # (user, reason) to e-mail after the database changes are saved
        self.notes = []
        counts = {"created": 0, "updated": 0, "unchanged": 0, "skipped": 0}
        with transaction.atomic():
            for person in people:
                counts[self.apply(person, resend_invites)] += 1
            if dry_run:
                transaction.set_rollback(True)

        if not dry_run:
            self.send_invites(no_invite)
        self.stdout.write("")
        for note in self.notes:
            self.stdout.write(self.style.WARNING(f"! {note}"))
        summary = ", ".join(f"{n} {k}" for k, n in counts.items())
        if dry_run:
            self.stdout.write(self.style.NOTICE(f"DRY RUN - nothing was saved. Would be: {summary}."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done: {summary}."))

    def say(self, line, style=None):
        self.stdout.write(style(line) if style else line)

    def apply(self, p, resend_invites):
        tag = f"{p['code'] + ' ' if p['code'] else ''}{p['name']} <{p['email']}>"
        user = User.objects.filter(email__iexact=p["email"]).first()

        if p["role"] is None:
            where = "has a login (role unchanged)" if user else "no login created"
            extra = self.link_employee(p, user, tag)
            if extra:
                audit.record(None, f"Team setup: {', '.join(extra)}"[:200], f"{p['name']} <{p['email']}>")
            self.say(f"- skipped   {tag}: no role in the file yet; {where}" + (f"; {'; '.join(extra)}" if extra else ""),
                     self.style.WARNING)
            return "skipped"

        role_label = " + ".join(Role(r).label for r in [p["role"], *p["extra_roles"]])
        if user is None:
            from apps.system.views import unique_username

            user = User(username=unique_username(p["email"]), email=p["email"], name=p["name"], role=p["role"],
                        extra_roles=p["extra_roles"])
            if p["role"] == Role.ADMIN:
                user.is_superuser = user.is_staff = True
            user.set_unusable_password()
            user.save()
            changes = ["created"]
            self.invites.append(user)
            outcome = "created"
        else:
            changes = []
            if user.is_superuser and p["role"] != Role.ADMIN:
                self.notes.append(f"{tag} is a Django superuser, so the file's role '{role_label}' was not applied. "
                                  "Remove 'superuser' in /admin/ first if this is intended.")
            else:
                if user.role != p["role"]:
                    changes.append(f"role {Role(user.role).label} -> {Role(p['role']).label}")
                    user.role = p["role"]
                if p["role"] != Role.ADMIN and sorted(user.all_roles[1:]) != sorted(p["extra_roles"]):
                    changes.append("extra roles: " + (", ".join(Role(r).label for r in p["extra_roles"]) or "none"))
                    user.extra_roles = p["extra_roles"]
            if p["role"] == Role.ADMIN and not (user.is_superuser and user.is_staff):
                user.is_superuser = user.is_staff = True
                changes.append("made superuser")
            if not user.name:
                user.name = p["name"]
                changes.append("name")
            if not user.is_active:
                self.notes.append(f"{tag} is deactivated in the portal; re-activate in Settings -> Users if needed.")
            if changes:
                user.save()
            if resend_invites and user.status == "invited":
                self.invites.append(user)
                changes.append("invitation re-sent")
            outcome = "updated" if changes else "unchanged"

        if p["perms"] is not None and user.effective_role != Role.ADMIN:
            if sorted(p["perms"]) != attendance_perms.granted(user):
                attendance_perms.set_granted(user, p["perms"])
                changes.append("attendance permissions: " + (", ".join(p["perms"]) or "none"))
                outcome = "updated" if outcome == "unchanged" else outcome

        changes += self.link_employee(p, user, tag)
        if changes and outcome == "unchanged":
            outcome = "updated"
        if changes:
            audit.record(None, f"Team setup: {', '.join(changes)}"[:200], f"{p['name']} <{p['email']}>")
        style = self.style.SUCCESS if outcome == "created" else (None if outcome == "updated" else self.style.HTTP_INFO)
        self.say(f"- {outcome:<10}{tag} [{role_label}]" + (f": {'; '.join(changes)}" if changes else ""), style)
        return outcome

    def link_employee(self, p, user, tag):
        """Creates / completes the Attendance employee and links it to the login. Returns change notes."""
        if not p["code"]:
            return []
        current = Employee.objects.filter(deleted_at__isnull=True)
        emp = current.filter(employee_code__iexact=p["code"]).first()
        changes = []
        if emp is None:
            other = current.filter(email__iexact=p["email"]).first()
            if other:
                self.notes.append(f"{tag}: an employee with this e-mail already exists as ID {other.employee_code}; "
                                  f"kept that record instead of creating ID {p['code']}.")
                emp = other
            else:
                emp = Employee.objects.create(employee_code=p["code"], name=p["name"], email=p["email"],
                                              joining_date=p["joining_date"])
                changes.append(f"employee {p['code']} added")
        else:
            if emp.email and emp.email.lower() != p["email"]:
                self.notes.append(f"{tag}: employee ID {emp.employee_code} has a different e-mail ({emp.email}); "
                                  "not linked. Check the Attendance -> Employees record.")
                return changes
            fill = {}
            if not emp.email:
                fill["email"] = p["email"]
            if not emp.joining_date and p["joining_date"]:
                fill["joining_date"] = p["joining_date"]
            if fill:
                for k, v in fill.items():
                    setattr(emp, k, v)
                emp.save(update_fields=[*fill, "updated_at"])
                changes.append("employee " + ", ".join(fill))

        if user is not None and emp.user_id != user.pk:
            if emp.user_id:
                self.notes.append(f"{tag}: employee {emp.employee_code} is linked to another login; left as is.")
            elif Employee.objects.filter(user=user).exclude(pk=emp.pk).exists():
                self.notes.append(f"{tag}: this login is already linked to another employee record; left as is.")
            else:
                emp.user = user
                emp.save(update_fields=["user", "updated_at"])
                changes.append(f"linked to employee {emp.employee_code}")
        return changes

    def send_invites(self, no_invite):
        from apps.system.views import send_invitation

        if self.invites and not no_invite and settings.EMAIL_BACKEND.endswith((".console.EmailBackend",
                                                                                 ".dummy.EmailBackend")):
            self.notes.append("E-mail sending is not set up (EMAIL_BACKEND in .env), so no invitation was really "
                              "sent. Share the set-password links printed above; they work for 3 days.")
            no_invite = True
        for user in self.invites:
            if no_invite:
                self.say(f"  set-password link for {user.email}: {set_password_link(user)}")
                continue
            try:
                send_invitation(user)
                self.say(f"  invitation e-mailed to {user.email}", self.style.SUCCESS)
            except Exception as exc:  # the account is saved; give the link so it can be shared by hand
                self.notes.append(f"Could not e-mail {user.email} ({exc.__class__.__name__}). "
                                  f"Share this set-password link with them: {set_password_link(user)}")
