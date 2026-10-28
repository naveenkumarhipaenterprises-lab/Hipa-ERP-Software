"""Manual attendance entry (Super Admin / Management) and Super-Admin-only deletes across modules."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase

from apps.attendance import window
from apps.attendance.models import AttendanceRecord, Employee
from apps.inventory.models import Product, StockMovement
from apps.inventory.services import move_stock
from apps.purchase.models import MaterialMovement, RawMaterial, Supplier
from apps.purchase.services import move_material
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user


class ManualAttendanceTests(TestCase):
    def setUp(self):
        self.worker = make_user("marketing", username="test_worker")
        self.emp = Employee.objects.create(employee_code="T08", name="TEST Worker", user=self.worker)
        self.day = (window.now() - timedelta(days=1)).date()
        self.url = f"{API}/attendance/records/"

    def entry(self, **extra):
        return {"employee_id": self.emp.pk, "date": str(self.day), "check_in": "09:45", "check_out": "17:40",
                "note": "Forgot to check in", **extra}

    def test_management_enters_attendance_for_someone(self):
        res = client_for(make_user("management")).post(self.url, self.entry(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        r = AttendanceRecord.objects.get(employee=self.emp, attendance_date=self.day)
        self.assertEqual(r.check_in_at.astimezone(window.IST).strftime("%H:%M"), "09:45")
        self.assertEqual(r.status, AttendanceRecord.Status.COMPLETED)
        self.assertEqual(res.data["entered_by"], "TEST management")
        self.assertEqual(res.data["note"], "Forgot to check in")
        self.assertTrue(AuditLog.objects.filter(action__startswith="Entered attendance").exists())

    def test_management_enters_attendance_for_themselves(self):
        mgmt_user = make_user("management", username="test_mgmt_self")
        mgmt_emp = Employee.objects.create(employee_code="M01", name="TEST Mgmt Self", user=mgmt_user)
        res = client_for(mgmt_user).post(self.url, {"employee_id": mgmt_emp.pk, "date": str(self.day),
                                                     "check_in": "09:30", "check_out": "17:30",
                                                     "note": "Self manual entry"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        r = AttendanceRecord.objects.get(employee=mgmt_emp, attendance_date=self.day)
        self.assertEqual(r.check_in_at.astimezone(window.IST).strftime("%H:%M"), "09:30")
        self.assertEqual(r.check_out_at.astimezone(window.IST).strftime("%H:%M"), "17:30")
        self.assertEqual(r.status, AttendanceRecord.Status.COMPLETED)
        self.assertEqual(res.data["entered_by"], mgmt_user.name)
        self.assertTrue(AuditLog.objects.filter(action__startswith="Entered attendance").exists())

    def test_correcting_an_existing_day_updates_it(self):
        api = client_for(make_user("admin"))
        api.post(self.url, self.entry(check_out=""), format="json")
        res = api.post(self.url, self.entry(check_in="09:10", check_out="18:00", note="Came late, forgot check-out"), format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(AttendanceRecord.objects.filter(employee=self.emp).count(), 1)
        self.assertTrue(AuditLog.objects.filter(action__startswith="Corrected attendance").exists())

    def test_team_roles_cannot_enter_attendance(self):
        for role in ("sales", "marketing", "finance"):
            res = client_for(make_user(role, username=f"test_{role}_e")).post(self.url, self.entry(), format="json")
            self.assertEqual(res.status_code, 403, role)

    def test_validation(self):
        api = client_for(make_user("management"))
        res = api.post(self.url, self.entry(note="", check_in="9am"), format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("note", res.data)
        self.assertIn("check_in", res.data)
        future = (window.now() + timedelta(days=2)).date()
        self.assertEqual(api.post(self.url, self.entry(date=str(future)), format="json").status_code, 400)

    def test_only_super_admin_deletes_attendance(self):
        rec = client_for(make_user("management")).post(self.url, self.entry(), format="json").data
        res = client_for(make_user("management", username="test_mgmt2")).delete(f"{self.url}{rec['id']}/")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["detail"], "Only a Super Admin can delete records.")
        self.assertEqual(client_for(make_user("admin")).delete(f"{self.url}{rec['id']}/").status_code, 204)
        self.assertFalse(AttendanceRecord.objects.filter(pk=rec["id"]).exists())


class SuperAdminDeleteTests(TestCase):
    def test_deleting_is_super_admin_only_everywhere(self):
        s = Supplier.objects.create(name="TEST Farms", city="Erode")
        for role in ("management", "purchase"):
            res = client_for(make_user(role, username=f"test_{role}_d")).delete(f"{API}/purchase/suppliers/{s.pk}/")
            self.assertEqual(res.status_code, 403, role)
        self.assertEqual(client_for(make_user("admin")).delete(f"{API}/purchase/suppliers/{s.pk}/").status_code, 204)

    def test_undo_manual_stock_movement_puts_stock_back(self):
        p = Product.objects.create(name="TEST Chilli Powder", price_per_kg=Decimal("300"))
        move_stock(p, "in", Decimal("10"))
        wrong = move_stock(p, "out", Decimal("4"))
        self.assertEqual(client_for(make_user("inventory")).delete(f"{API}/inventory/movements/{wrong.pk}/").status_code, 403)
        self.assertEqual(client_for(make_user("admin")).delete(f"{API}/inventory/movements/{wrong.pk}/").status_code, 204)
        p.refresh_from_db()
        self.assertEqual(p.stock_kg, Decimal("10"))
        sale = move_stock(p, "out", Decimal("1"), source=StockMovement.Source.SALE, reference="SO-1")
        self.assertEqual(client_for(make_user("admin", username="a2")).delete(f"{API}/inventory/movements/{sale.pk}/").status_code, 400)

    def test_undo_material_movement(self):
        m = RawMaterial.objects.create(name="TEST Pepper", category="whole_spice", unit="kg")
        move_material(m, "in", Decimal("20"))
        used = move_material(m, "out", Decimal("5"), source=MaterialMovement.Source.USAGE)
        self.assertEqual(client_for(make_user("admin")).delete(f"{API}/purchase/material-movements/{used.pk}/").status_code, 204)
        m.refresh_from_db()
        self.assertEqual(m.current_stock, Decimal("20"))
