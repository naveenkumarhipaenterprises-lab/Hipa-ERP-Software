"""CSV downloads with a file name the frontend can read (Content-Disposition is exposed via CORS)."""
import csv
import io

from django.http import HttpResponse


def csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if v is None else v for v in row])
    # BOM so Excel shows ₹ and Indian-language text correctly
    response = HttpResponse("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
