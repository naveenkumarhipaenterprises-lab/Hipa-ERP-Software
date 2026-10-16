"""Customers: GSTIN and shipping address in add / edit, import and export. TEST records only."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.customers.models import Customer

from .helpers import API, client_for, make_user


class CustomerGstinShippingTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("sales", username="seller"))

    def test_saved_shown_and_checked(self):
        res = self.api.post(f"{API}/customers/", {"name": "TEST Traders", "type": "retailer", "city": "Erode",
                                                  "gstin": "33abcde1234f1z5", "shipping_address": "TEST godown, Erode"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual((res.data["gstin"], res.data["shipping_address"]), ("33ABCDE1234F1Z5", "TEST godown, Erode"))
        bad = self.api.post(f"{API}/customers/", {"name": "TEST Two", "type": "retailer", "city": "Erode", "gstin": "12345"}, format="json")
        self.assertIn("gstin", bad.data)
        cleared = self.api.patch(f"{API}/customers/{res.data['id']}/", {"shipping_address": ""}, format="json")
        self.assertEqual(cleared.data["shipping_address"], "")

    def test_import_template_and_export_include_them(self):
        template = self.api.get(f"{API}/customers/import/template/").content.decode()
        self.assertIn("shipping_address,gstin", template)
        csv_text = "name,type,city,shipping_address,gstin\nTEST Mart,retailer,Salem,TEST back gate,33ABCDE1234F1Z5\n"
        res = self.api.post(f"{API}/customers/import/", {"file": SimpleUploadedFile("c.csv", csv_text.encode(), "text/csv")}, format="multipart")
        self.assertEqual((res.status_code, res.data["created"]), (200, 1))
        c = Customer.objects.get(name="TEST Mart")
        self.assertEqual((c.gstin, c.shipping_address), ("33ABCDE1234F1Z5", "TEST back gate"))
        export = self.api.get(f"{API}/customers/export/").content.decode()
        self.assertIn("Shipping address,GSTIN", export)
        self.assertIn("33ABCDE1234F1Z5", export)
