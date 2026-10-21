"""Customer import limits (checked on the server, not only in the browser) and the inventory export filters."""
import csv
import io
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.customers.models import Customer
from apps.inventory.models import Product

from .helpers import API, client_for, make_user

HEADER = "name,type,contact_person,phone,email,city,address\n"


class CustomerImportLimitTests(TestCase):
    def setUp(self):
        self.api = client_for(make_user("admin"))

    def upload(self, name, content):
        return self.api.post(f"{API}/customers/import/", {"file": SimpleUploadedFile(name, content)}, format="multipart")

    def test_file_over_5_mb_is_refused_by_the_server(self):
        big = (HEADER + "TEST A,retailer,,,,Salem,\n").encode() + b" " * (5 * 1024 * 1024)
        res = self.upload("big.csv", big)
        self.assertEqual(res.status_code, 400)
        self.assertIn("larger than 5 MB", str(res.data))
        self.assertFalse(Customer.objects.exists())

    def test_too_many_rows_are_refused_before_anything_is_saved(self):
        with mock.patch("apps.customers.views.MAX_IMPORT_ROWS", 3):
            res = self.upload("c.csv", (HEADER + "".join(f"TEST {i},retailer,,,,Salem,\n" for i in range(4))).encode())
        self.assertEqual(res.status_code, 400)
        self.assertIn("more than 3 rows", str(res.data))
        self.assertFalse(Customer.objects.exists())

    def test_excel_file_is_imported(self):
        from openpyxl import Workbook

        wb = Workbook()
        wb.active.append(HEADER.strip().split(","))
        wb.active.append(["TEST Excel", "retailer", "", "", "", "Salem", ""])
        buf = io.BytesIO()
        wb.save(buf)
        res = self.upload("c.xlsx", buf.getvalue())
        self.assertEqual((res.status_code, res.data["created"]), (200, 1))


class InventoryExportFilterTests(TestCase):
    def test_export_contains_only_the_products_the_list_shows(self):
        Product.objects.create(name="TEST Turmeric", price_per_kg=250, stock_kg=100)
        Product.objects.create(name="TEST Chilli", price_per_kg=300, stock_kg=100)
        Product.objects.create(name="TEST Old Pepper", price_per_kg=400, is_active=False)
        api = client_for(make_user("admin"))

        def names(params):
            res = api.get(f"{API}/inventory/items/export/", params)
            self.assertEqual(res.status_code, 200)
            text = b"".join(res.streaming_content if res.streaming else [res.content]).decode("utf-8-sig")
            return [row[0] for row in csv.reader(io.StringIO(text))][1:]

        self.assertEqual(names({}), ["TEST Chilli", "TEST Turmeric"])
        self.assertEqual(names({"search": "turm"}), ["TEST Turmeric"])
        self.assertEqual(names({"active": "false"}), ["TEST Old Pepper"])
