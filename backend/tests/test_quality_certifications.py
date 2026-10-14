"""
Quality → Certifications: add / view / edit / delete, with the certificate document (PDF, JPG, PNG; at most 4 MB)
saved in the same row and opened only through a permission-checked endpoint. TEST records only.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.core.periods import today
from apps.quality.models import Certification
from apps.system.models import AuditLog

from .helpers import API, client_for, make_user

PDF = b"%PDF-1.4\n% TEST certificate\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def pdf(name="TEST-fssai.pdf", content=PDF):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


class CertificationTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("quality", username="qa"))

    def create(self, expected=201, **fields):
        body = {"name": "TEST FSSAI License", "issuing_authority": "TEST FSSAI", "certificate_number": "TEST-12345",
                "category": "fssai", "issue_date": (today() - timedelta(days=30)).isoformat(),
                "valid_until": (today() + timedelta(days=365)).isoformat(), **fields}
        res = self.api.post(f"{API}/quality/certifications/", {k: v for k, v in body.items() if v is not None}, format="multipart")
        self.assertEqual(res.status_code, expected, res.data)
        return res.data

    def listed(self):
        return self.api.get(f"{API}/quality/certifications/").data

    def test_empty_list(self):
        self.assertEqual(self.listed(), [])
        self.assertEqual(self.api.get(f"{API}/quality/overview/").data["certifications"], [])

    def test_create_with_document_then_view_and_download_it(self):
        c = self.create(document=pdf())
        self.assertEqual((c["name"], c["status"], c["category"], c["document"]["name"], c["document"]["size"]),
                         ("TEST FSSAI License", "Active", "FSSAI License", "TEST-fssai.pdf", len(PDF)))
        self.assertEqual([r["id"] for r in self.listed()], [c["id"]])  # still there after a reload
        self.assertEqual(self.api.get(f"{API}/quality/overview/").data["certifications"][0]["id"], c["id"])
        shown = self.api.get(f"{API}/quality/certifications/{c['id']}/document/")
        self.assertEqual((shown.status_code, shown["Content-Type"], shown.content), (200, "application/pdf", PDF))
        self.assertTrue(shown["Content-Disposition"].startswith("inline"))
        saved = self.api.get(f"{API}/quality/certifications/{c['id']}/document/?download=1")
        self.assertEqual(saved["Content-Disposition"], 'attachment; filename="TEST-fssai.pdf"')
        self.assertTrue(AuditLog.objects.filter(action="Added certification").exists())

    def test_statuses_follow_the_saved_data(self):
        soon = self.create(name="TEST soon", valid_until=(today() + timedelta(days=20)).isoformat())
        gone = self.create(name="TEST gone", issue_date=(today() - timedelta(days=400)).isoformat(),
                           valid_until=(today() - timedelta(days=1)).isoformat())
        pending = self.create(name="TEST pending", status="pending")
        self.assertEqual((soon["status"], gone["status"], pending["status"]), ("Expiring Soon", "Expired", "Pending Verification"))

    def test_invalid_input_is_refused_and_nothing_is_saved(self):
        cases = [
            ({"name": ""}, "name"),
            ({"valid_until": (today() - timedelta(days=60)).isoformat()}, "valid_until"),  # before the issue date
            ({"issue_date": (today() + timedelta(days=1)).isoformat(), "valid_until": None}, "issue_date"),
            ({"category": "nope"}, "category"),
            ({"document": SimpleUploadedFile("TEST.exe", b"MZ", content_type="application/octet-stream")}, "document"),
            ({"document": pdf(content=b"not really a pdf")}, "document"),  # renamed file
            ({"document": pdf(content=b"")}, "document"),
            ({"document": pdf(content=b"%PDF-" + b"0" * (4 * 1024 * 1024))}, "document"),  # over 4 MB
        ]
        for fields, field in cases:
            err = self.create(expected=400, **fields)
            self.assertIn(field, err, fields)
        self.assertFalse(Certification.objects.exists())

    def test_edit_updates_the_same_record_and_can_replace_or_remove_the_document(self):
        c = self.create(document=pdf())
        res = self.api.patch(f"{API}/quality/certifications/{c['id']}/", {"certificate_number": "TEST-999",
                                                                          "document": SimpleUploadedFile("TEST-scan.png", PNG, content_type="image/png")},
                             format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual((res.data["certificate_number"], res.data["name"], res.data["document"]["name"]),
                         ("TEST-999", "TEST FSSAI License", "TEST-scan.png"))
        self.assertEqual(Certification.objects.count(), 1)  # no duplicate
        self.assertEqual(self.api.get(f"{API}/quality/certifications/{c['id']}/document/").content, PNG)
        bad = self.api.patch(f"{API}/quality/certifications/{c['id']}/", {"valid_until": "2000-01-01"}, format="multipart")
        self.assertIn("valid_until", bad.data)
        removed = self.api.patch(f"{API}/quality/certifications/{c['id']}/", {"remove_document": "true"}, format="multipart")
        self.assertIsNone(removed.data["document"])
        self.assertEqual(self.api.get(f"{API}/quality/certifications/{c['id']}/document/").status_code, 404)

    def test_delete_removes_only_that_certification(self):
        keep, drop = self.create(name="TEST keep", document=pdf()), self.create(name="TEST drop", document=pdf())
        self.assertEqual(self.api.delete(f"{API}/quality/certifications/{drop['id']}/").status_code, 204)
        self.assertEqual([r["id"] for r in self.listed()], [keep["id"]])
        self.assertEqual(self.api.get(f"{API}/quality/certifications/{drop['id']}/document/").status_code, 404)
        self.assertEqual(self.api.get(f"{API}/quality/certifications/{keep['id']}/document/").status_code, 200)

    def test_only_quality_users_can_read_or_change(self):
        c = self.create(document=pdf())
        sales = client_for(make_user("sales", username="seller"))
        self.assertEqual(sales.get(f"{API}/quality/certifications/").status_code, 403)
        self.assertEqual(sales.get(f"{API}/quality/certifications/{c['id']}/document/").status_code, 403)
        self.assertEqual(sales.delete(f"{API}/quality/certifications/{c['id']}/").status_code, 403)
        anonymous = self.client.get(f"{API}/quality/certifications/{c['id']}/document/")
        self.assertEqual(anonymous.status_code, 401)
        self.assertTrue(Certification.objects.filter(pk=c["id"]).exists())
