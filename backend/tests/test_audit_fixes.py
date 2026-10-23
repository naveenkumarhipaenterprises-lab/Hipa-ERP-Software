"""
Fixes from the 14 Oct 2026 audit: deleting a GRN-linked quality test puts the GRN's status back, a GRN can't be
deleted from under its purchase returns, nobody but a Super Admin changes their own Attendance permissions, and
importing customers never blanks saved details. TEST records only.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.attendance import permissions as attendance_perms
from apps.core.periods import today
from apps.customers.models import Customer
from apps.purchase.models import GoodsReceipt, Purchase, RawMaterial

from .helpers import API, client_for, make_user


class Base(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def call(self, method, path, body=None, expected=200, fmt="json"):
        res = getattr(self.api, method)(API + path, body or {}, format=fmt)
        self.assertEqual(res.status_code, expected, f"{method.upper()} {path}: {getattr(res, 'data', '')}")
        return getattr(res, "data", None)

    def purchase(self, qty=100):
        s = self.call("post", "/purchase/suppliers/", {"name": "TEST Farms", "city": "Erode"}, 201)
        m = self.call("post", "/purchase/raw-materials/", {"name": "TEST Raw Pepper", "category": "whole_spice", "unit": "kg",
                                                            "minimum_stock": 0, "reorder_level": 0}, 201)
        p = self.call("post", "/purchase/purchases/", {"supplier_id": s["id"], "item_type": "material", "material_id": m["id"],
                                                       "quantity": qty, "unit_price": 500, "purchase_date": today().isoformat()}, 201)
        return m, p

    def receive(self, p, qty):
        return self.call("post", "/purchase/goods-receipts/", {"purchase_id": p["id"], "received_date": today().isoformat(),
                                                               "received_quantity": qty}, 201)


class QualityTestDeleteTests(Base):
    def record_test(self, grn, result):
        return self.call("post", "/quality/tests/", {"goods_receipt_id": grn["id"], "test_date": today().isoformat(), "result": result,
                                                     "readings": [{"parameter": "Moisture", "value": "11"}]}, 201)

    def status(self, grn):
        return GoodsReceipt.objects.get(pk=grn["id"]).quality_status

    def test_deleting_a_test_puts_the_grn_status_back(self):
        _m, p = self.purchase()
        grn = self.receive(p, 100)
        first = self.record_test(grn, "pass")
        second = self.record_test(grn, "fail")
        self.assertEqual(self.status(grn), "failed")
        self.call("delete", f"/records/quality_test/{second['id']}/", expected=204)
        self.assertEqual(self.status(grn), "passed")  # the remaining (latest) test decides again
        self.call("delete", f"/records/quality_test/{first['id']}/", expected=204)
        self.assertEqual(self.status(grn), "pending")  # no test left: waiting for inspection, not "Passed"

    def test_a_test_without_a_grn_still_deletes(self):
        _m, p = self.purchase()
        material = Purchase.objects.get(pk=p["id"]).material_id
        t = self.call("post", "/quality/tests/", {"material_id": material, "test_date": today().isoformat(), "result": "pass",
                                                  "parameters": "TEST"}, 201)
        self.call("delete", f"/records/quality_test/{t['id']}/", expected=204)


class GoodsReceiptReturnTests(Base):
    def test_a_grn_cant_be_deleted_from_under_its_returns(self):
        m, p = self.purchase(qty=100)
        first, second = self.receive(p, 60), self.receive(p, 40)
        self.call("post", "/purchase/returns/", {"purchase_id": p["id"], "quantity": 50, "return_date": today().isoformat(),
                                                 "reason": "quality"}, 201)
        err = self.call("delete", f"/records/goods_receipt/{first['id']}/", expected=400)  # only 40 would be left for 50 returned
        self.assertIn("Cancel or delete those returns first", err["detail"])
        self.assertEqual(Purchase.objects.get(pk=p["id"]).received_quantity, 100)  # nothing changed
        self.call("delete", f"/records/goods_receipt/{second['id']}/", expected=204)  # 60 still covers the 50 returned
        self.assertEqual(Purchase.objects.get(pk=p["id"]).received_quantity, 60)
        self.assertEqual(RawMaterial.objects.get(pk=m["id"]).current_stock, 10)  # 100 in, 50 returned, 40 taken back


class OwnAttendancePermissionTests(Base):
    def test_only_a_super_admin_changes_their_own(self):
        manager = make_user("management", username="manager")
        attendance_perms.set_granted(manager, ["leave_apply"])
        api = client_for(manager)
        res = api.patch(f"{API}/settings/users/{manager.id}/", {"attendance_permissions": ["leave_apply", "settings_manage"]}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(attendance_perms.granted(manager), ["leave_apply"])
        same = api.patch(f"{API}/settings/users/{manager.id}/", {"name": "TEST Manager", "attendance_permissions": ["leave_apply"]},
                         format="json")
        self.assertEqual(same.status_code, 200)  # unchanged permissions don't block other edits
        other = make_user("sales", username="seller")
        res = api.patch(f"{API}/settings/users/{other.id}/", {"attendance_permissions": ["leave_apply"]}, format="json")
        self.assertEqual(res.status_code, 200)  # other people's still work
        self.assertEqual(attendance_perms.granted(other), ["leave_apply"])


class CustomerImportTests(Base):
    def upload(self, text):
        return self.call("post", "/customers/import/", {"file": SimpleUploadedFile("c.csv", text.encode(), "text/csv")}, fmt="multipart")

    def test_empty_cells_never_erase_saved_details(self):
        self.call("post", "/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode", "phone": "9876543210",
                                          "email": "test@test.invalid", "address": "TEST street"}, 201)
        res = self.upload("name,type,contact_person,phone,email,city,address\nTEST Traders,,,,,Erode,\n")
        self.assertEqual((res["updated"], res["errors"]), (1, []))
        c = Customer.objects.get(name="TEST Traders")
        self.assertEqual((c.phone, c.email, c.address, c.type), ("9876543210", "test@test.invalid", "TEST street", "retailer"))
        self.upload("name,type,contact_person,phone,email,city,address\nTEST Traders,,,,new@test.invalid,Erode,\n")
        self.assertEqual(Customer.objects.get(name="TEST Traders").email, "new@test.invalid")  # a filled cell still updates


class ManualAttendanceEntryTests(Base):
    """Manual entries: managers may enter their own attendance, evening check-ins on the right day, corrections move the record."""

    def setUp(self):
        super().setUp()
        from datetime import timedelta

        from apps.attendance import window
        from apps.attendance.models import Employee

        self.window = window
        self.worker = make_user("sales", username="worker")
        self.emp = Employee.objects.create(employee_code="T-W", name="TEST Worker", user=self.worker)
        self.day = (window.now() - timedelta(days=3)).date()
        self.url = f"{API}/attendance/records/"

    def entry(self, **extra):
        return {"employee_id": self.emp.pk, "date": str(self.day), "check_in": "09:45", "check_out": "17:40", "note": "TEST", **extra}

    def test_managers_can_enter_their_own_attendance(self):
        from apps.attendance.models import AttendanceRecord, Employee

        boss = make_user("management", username="boss")
        own = Employee.objects.create(employee_code="T-B", name="TEST Boss", user=boss)
        res = client_for(boss).post(self.url, self.entry(employee_id=own.pk), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(AttendanceRecord.objects.get(employee=own).entered_by, boss)  # still marked as a manual entry
        self.assertEqual(client_for(boss).post(self.url, self.entry(), format="json").status_code, 201)  # someone else too

    def test_an_evening_check_in_belongs_to_the_evening_before(self):
        res = self.api.post(self.url, self.entry(check_in="18:00", check_out="17:30"), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        from apps.attendance.models import AttendanceRecord

        r = AttendanceRecord.objects.get(employee=self.emp)
        ist = self.window.IST
        self.assertEqual(r.attendance_date, self.day)
        self.assertEqual((r.check_in_at.astimezone(ist).date(), r.check_in_at.astimezone(ist).strftime("%H:%M")),
                         (self.day - self.window.DAY, "18:00"))  # like a self check-in at 6 PM for the next work day
        self.assertEqual(r.check_out_at.astimezone(ist).date(), self.day)

    def test_correcting_the_date_moves_the_record(self):
        from apps.attendance.models import AttendanceRecord

        first = self.api.post(self.url, self.entry(), format="json").data
        moved_to = self.day - self.window.DAY
        res = self.api.post(self.url, self.entry(record_id=first["id"], date=str(moved_to)), format="json")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(list(AttendanceRecord.objects.filter(employee=self.emp).values_list("id", "attendance_date")),
                         [(first["id"], moved_to)])  # the same record, not a second one
        other = self.api.post(self.url, self.entry(), format="json").data  # a record on the original day again
        clash = self.api.post(self.url, self.entry(record_id=other["id"], date=str(moved_to)), format="json")
        self.assertEqual(clash.status_code, 400)
        self.assertIn("already has a record", clash.data["date"][0])

    def test_unknown_leave_action_is_not_found(self):
        from apps.attendance.models import LeaveRequest

        lr = LeaveRequest.objects.create(employee=self.emp, type="leave", date=self.day, reason="TEST")
        self.assertEqual(self.api.post(f"{API}/attendance/leave/{lr.pk}/nonsense/").status_code, 404)


class SupplierPaymentStatusTests(Base):
    def pay(self, p, amount):
        return self.call("post", "/purchase/payments/", {"purchase_id": p["id"], "amount": amount, "payment_date": today().isoformat(),
                                                          "payment_method": "upi"}, 201)

    def label(self, payment):
        from apps.purchase.models import SupplierPayment

        return SupplierPayment.objects.get(pk=payment["id"]).get_status_display()

    def test_labels_follow_what_is_still_owed(self):
        _m, p = self.purchase(qty=10)  # 10 kg x 500
        total = Purchase.objects.get(pk=p["id"]).total_amount
        first = self.pay(p, total / 2)
        second = self.pay(p, total / 2)
        self.assertEqual((self.label(first), self.label(second)), ("Partially Paid", "Paid"))
        self.call("post", f"/purchase/payments/{first['id']}/cancel/", expected=200)
        self.assertEqual(self.label(second), "Partially Paid")  # it no longer settles the purchase
        third = self.pay(p, total / 2)
        self.assertEqual((self.label(second), self.label(third)), ("Partially Paid", "Paid"))


class HealthCheckTests(TestCase):
    def test_open_to_everyone_and_reports_the_database(self):
        res = self.client.get(f"{API}/health/")
        self.assertEqual((res.status_code, res.json()), (200, {"status": "ok", "database": "ok"}))
        self.assertEqual(res["Cache-Control"], "no-store")

    def test_database_down_is_503(self):
        from unittest import mock

        with mock.patch("django.db.backends.utils.CursorWrapper.execute", side_effect=Exception("TEST down")):
            res = self.client.get(f"{API}/health/")
        self.assertEqual((res.status_code, res.json()["status"]), (503, "unavailable"))
