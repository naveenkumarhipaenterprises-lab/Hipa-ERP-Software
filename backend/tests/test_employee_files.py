"""Deleting a user (Settings -> Users) and the employee photo / documents endpoints."""
import io

from django.test import TestCase

from apps.accounts.models import User
from apps.attendance import permissions as attendance_perms
from apps.attendance.models import AttendanceRecord, Employee, EmployeeFile

from .helpers import API, client_for, make_user

USERS = f"{API}/settings/users"


def upload(name, content=b"x" * 10):
    f = io.BytesIO(content)
    f.name = name
    return f


def files_url(emp, fid=None):
    return f"{API}/attendance/employees/{emp.id}/files/" + (f"{fid}/" if fid else "")


class DeleteUserTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.api = client_for(self.admin)

    def test_deleting_a_user_keeps_the_attendance_history(self):
        user = make_user("sales", username="test_leaver")
        emp = Employee.objects.create(employee_code="T31", name=user.name, user=user)
        AttendanceRecord.objects.create(employee=emp, attendance_date="2026-10-20", check_in_at="2026-10-20T03:40:00Z")
        res = self.api.delete(f"{USERS}/{user.pk}/")
        self.assertEqual(res.status_code, 204, getattr(res, "data", res))
        self.assertFalse(User.objects.filter(pk=user.pk).exists())
        emp.refresh_from_db()
        self.assertIsNotNone(emp.deleted_at)
        self.assertEqual((emp.status, emp.user), (Employee.Status.INACTIVE, None))
        self.assertEqual(emp.attendance.count(), 1)

    def test_who_may_delete(self):
        user = make_user("sales", username="test_target")
        self.assertEqual(client_for(make_user("sales", username="test_other")).delete(f"{USERS}/{user.pk}/").status_code, 403)
        self.assertEqual(self.api.delete(f"{USERS}/{self.admin.pk}/").status_code, 400)  # not yourself
        other_admin = make_user("admin", username="test_admin2")
        self.assertEqual(self.api.delete(f"{USERS}/{other_admin.pk}/").status_code, 403)  # Super Admins: owner only
        owner = User.objects.create_superuser(username="owner", email="owner@test.invalid", password="Test-Passw0rd!9", name="TEST Owner")
        self.assertEqual(client_for(owner).delete(f"{USERS}/{other_admin.pk}/").status_code, 204)
        self.assertEqual(self.api.delete(f"{USERS}/{user.pk}/").status_code, 204)

    def test_management_cannot_delete(self):
        # Deleting anything is for Super Admins across the whole app; Management deactivates users instead
        user = make_user("quality", username="test_q")
        self.assertEqual(client_for(make_user("management")).delete(f"{USERS}/{user.pk}/").status_code, 403)


class EmployeeFileTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin")
        self.api = client_for(self.admin)
        self.worker = make_user("attendance", username="test_worker")
        self.emp = Employee.objects.create(employee_code="T41", name=self.worker.name, user=self.worker)

    def test_upload_list_download_delete_a_document(self):
        res = self.api.post(files_url(self.emp), {"file": upload("aadhaar.pdf", b"%PDF-fake"), "kind": "document"}, format="multipart")
        self.assertEqual(res.status_code, 201, res.data)
        fid = res.data["id"]
        self.assertEqual((res.data["name"], res.data["kind"], res.data["content_type"]), ("aadhaar.pdf", "document", "application/pdf"))
        rows = self.api.get(files_url(self.emp)).data["results"]
        self.assertEqual([r["id"] for r in rows], [fid])
        download = self.api.get(files_url(self.emp, fid))
        self.assertEqual((download.status_code, download["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(download.content, b"%PDF-fake")
        self.assertEqual(self.api.delete(files_url(self.emp, fid)).status_code, 204)
        self.assertFalse(EmployeeFile.objects.exists())

    def test_a_new_photo_replaces_the_old_one(self):
        first = self.api.post(files_url(self.emp), {"file": upload("one.png"), "kind": "photo"}, format="multipart")
        second = self.api.post(files_url(self.emp), {"file": upload("two.jpg"), "kind": "photo"}, format="multipart")
        self.assertEqual((first.status_code, second.status_code), (201, 201))
        photos = EmployeeFile.objects.filter(kind="photo")
        self.assertEqual([p.name for p in photos], ["two.jpg"])

    def test_validation(self):
        res = self.api.post(files_url(self.emp), {"file": upload("virus.exe")}, format="multipart")
        self.assertEqual(res.status_code, 400)
        res = self.api.post(files_url(self.emp), {"file": upload("doc.pdf", b"x" * (5 * 1024 * 1024 + 1))}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("too big", str(res.data))
        res = self.api.post(files_url(self.emp), {"file": upload("sheet.pdf"), "kind": "photo"}, format="multipart")
        self.assertEqual(res.status_code, 400)  # a photo must be an image
        self.assertEqual(self.api.post(files_url(self.emp), {}, format="multipart").status_code, 400)  # no file

    def test_an_employee_reaches_their_own_files_and_nobody_elses(self):
        mine = self.api.post(files_url(self.emp), {"file": upload("payslip.pdf")}, format="multipart").data
        other = Employee.objects.create(employee_code="T42", name="TEST Other")
        theirs = self.api.post(files_url(other), {"file": upload("secret.pdf")}, format="multipart").data
        worker_api = client_for(self.worker)
        self.assertEqual(worker_api.get(files_url(self.emp)).status_code, 200)
        self.assertEqual(worker_api.post(files_url(self.emp), {"file": upload("photo.png"), "kind": "photo"}, format="multipart").status_code, 201)
        self.assertEqual(worker_api.get(files_url(self.emp, mine["id"])).status_code, 200)
        self.assertEqual(worker_api.get(files_url(other)).status_code, 403)
        self.assertEqual(worker_api.get(files_url(other, theirs["id"])).status_code, 403)
        self.assertEqual(worker_api.delete(files_url(other, theirs["id"])).status_code, 403)

    def test_a_viewer_views_but_does_not_manage(self):
        viewer = make_user("management", username="test_viewer")
        attendance_perms.set_granted(viewer, ["employee_view"])
        api = client_for(viewer)
        fid = self.api.post(files_url(self.emp), {"file": upload("contract.docx")}, format="multipart").data["id"]
        self.assertEqual(api.get(files_url(self.emp)).status_code, 200)
        self.assertEqual(api.get(files_url(self.emp, fid)).status_code, 200)
        self.assertEqual(api.post(files_url(self.emp), {"file": upload("new.pdf")}, format="multipart").status_code, 403)
        self.assertEqual(api.delete(files_url(self.emp, fid)).status_code, 403)
