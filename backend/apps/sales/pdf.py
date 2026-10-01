"""
Quotation and invoice PDFs (fpdf2). Company details come from Settings → Company Profile and
Tax & Billing; only filled-in details are printed. Noto Sans (SIL OFL, assets/fonts) prints ₹.
"""
import logging
from pathlib import Path

from django.conf import settings
from fpdf import FPDF
from fpdf.fonts import FontFace

from apps.core.money import inr
from apps.system.models import BillingSettings, CompanySettings

logging.getLogger("fontTools").setLevel(logging.WARNING)  # font subsetting logs every glyph at INFO

ASSETS = Path(settings.BASE_DIR) / "assets"
FONT = "NotoSans"
INK = (33, 33, 33)
MUTED = (110, 110, 110)
ACCENT = (139, 26, 26)  # HIPA red
RULE = (220, 220, 220)


def qty(value):
    text = f"{value:,.3f}".rstrip("0").rstrip(".")
    return f"{text} kg"


def pct(value):
    return f"{value.normalize():f}%"


class DocumentPDF(FPDF):
    def __init__(self, company):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.company = company
        self.add_font(FONT, "", str(ASSETS / "fonts" / "NotoSans-Regular.ttf"))
        self.add_font(FONT, "B", str(ASSETS / "fonts" / "NotoSans-Bold.ttf"))
        self.set_margins(14, 14, 14)
        self.set_auto_page_break(True, margin=18)
        self.alias_nb_pages()

    def footer(self):
        self.set_y(-12)
        self.set_font(FONT, "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 5, f"Page {self.page_no()} of {{nb}}", align="C")


def company_lines(company):
    lines = []
    if company.legal_name and company.legal_name != company.company_name:
        lines.append(company.legal_name)
    if company.address:
        lines.extend(l.strip() for l in company.address.splitlines() if l.strip())
    contact = " · ".join(x for x in (company.phone, company.email, company.website) if x)
    if contact:
        lines.append(contact)
    if company.gstin:
        lines.append(f"GSTIN: {company.gstin}")
    return lines


def header(pdf, company, title, meta):
    """Logo + company on the left, document title and number/date block on the right."""
    top = pdf.get_y()
    logo = ASSETS / "hipa-logo.png"
    x_text = pdf.l_margin
    if logo.exists():
        pdf.image(str(logo), x=pdf.l_margin, y=top, w=24, h=24)
        x_text += 28
    pdf.set_xy(x_text, top)
    pdf.set_font(FONT, "B", 15)
    pdf.set_text_color(*ACCENT)
    pdf.cell(95, 7, company.company_name or "HIPA MASALA", new_x="LEFT", new_y="NEXT")
    pdf.set_font(FONT, "", 8.5)
    pdf.set_text_color(*INK)
    for line in company_lines(company):
        pdf.set_x(x_text)
        pdf.multi_cell(95, 4.2, line, new_x="LEFT", new_y="NEXT")
    left_bottom = pdf.get_y()

    pdf.set_xy(pdf.w - pdf.r_margin - 70, top)
    pdf.set_font(FONT, "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(70, 8, title, align="R", new_x="LEFT", new_y="NEXT")
    pdf.set_font(FONT, "", 9)
    for label, value in meta:
        pdf.set_x(pdf.w - pdf.r_margin - 70)
        pdf.set_text_color(*MUTED)
        pdf.cell(32, 5, label, align="R")
        pdf.set_text_color(*INK)
        pdf.cell(38, 5, value, align="R", new_x="LEFT", new_y="NEXT")
        pdf.set_x(pdf.w - pdf.r_margin - 70)
    pdf.set_y(max(left_bottom, pdf.get_y(), top + 26) + 3)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.5)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)


def party_block(pdf, doc):
    def lines(address_label, address):
        out = [doc.customer_name]
        if doc.company_name and doc.company_name != doc.customer_name:
            out.append(doc.company_name)
        out.extend(l.strip() for l in (address or "").splitlines() if l.strip())
        if address_label == "bill":
            contact = " · ".join(x for x in (doc.phone, doc.email) if x)
            if contact:
                out.append(contact)
            if doc.gstin:
                out.append(f"GSTIN: {doc.gstin}")
        return out

    width = (pdf.w - pdf.l_margin - pdf.r_margin - 6) / 2
    top = pdf.get_y()
    bottoms = []
    for i, (heading, key, address) in enumerate((("Bill to", "bill", doc.billing_address),
                                                 ("Ship to", "ship", doc.shipping_address or doc.billing_address))):
        x = pdf.l_margin + i * (width + 6)
        pdf.set_xy(x, top)
        pdf.set_font(FONT, "B", 8.5)
        pdf.set_text_color(*MUTED)
        pdf.cell(width, 5, heading.upper(), new_x="LEFT", new_y="NEXT")
        pdf.set_text_color(*INK)
        for n, line in enumerate(lines(key, address)):
            pdf.set_font(FONT, "B" if n == 0 else "", 9.5 if n == 0 else 8.5)
            pdf.set_x(x)
            pdf.multi_cell(width, 4.4, line, new_x="LEFT", new_y="NEXT")
        bottoms.append(pdf.get_y())
    pdf.set_y(max(bottoms) + 5)


def items_table(pdf, doc):
    pdf.set_font(FONT, "", 8.5)
    pdf.set_text_color(*INK)
    pdf.set_draw_color(*RULE)
    pdf.set_line_width(0.2)
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=ACCENT)
    with pdf.table(col_widths=(8, 62, 22, 25, 14, 14, 30), text_align=("CENTER", "LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"),
                   headings_style=heading, line_height=5.5, padding=1.5, borders_layout="HORIZONTAL_LINES") as table:
        table.row(["#", "Product", "Quantity", "Unit price", "Disc.", "GST", "Amount"])
        for n, item in enumerate(doc.items.select_related("product"), start=1):
            table.row([str(n), item.product.name, qty(item.quantity_kg), inr(item.unit_price), pct(item.discount_pct),
                       pct(item.gst_pct), inr(item.total)])
    pdf.ln(3)


def totals_block(pdf, rows):
    width = 80
    x = pdf.w - pdf.r_margin - width
    for label, value, strong in rows:
        pdf.set_x(x)
        pdf.set_font(FONT, "B" if strong else "", 10 if strong else 9)
        pdf.set_text_color(*(ACCENT if strong else INK))
        pdf.cell(width - 38, 6, label, align="R")
        pdf.cell(38, 6, value, align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)
    pdf.ln(3)


def text_section(pdf, title, text):
    if not text:
        return
    pdf.set_font(FONT, "B", 9)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5.5, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(FONT, "", 8.5)
    pdf.multi_cell(0, 4.4, text, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)


def signature(pdf, company, billing):
    if pdf.get_y() > pdf.h - 50:
        pdf.add_page()
    pdf.ln(6)
    width = 70
    x = pdf.w - pdf.r_margin - width
    pdf.set_x(x)
    pdf.set_font(FONT, "B", 9)
    pdf.cell(width, 5, f"For {company.company_name or 'HIPA MASALA'}", align="C", new_x="LEFT", new_y="NEXT")
    pdf.ln(14)
    pdf.set_draw_color(*MUTED)
    pdf.line(x + 5, pdf.get_y(), x + width - 5, pdf.get_y())
    pdf.set_x(x)
    pdf.set_font(FONT, "", 8.5)
    pdf.cell(width, 5, billing.authorised_signatory or "Authorised signatory", align="C", new_x="LEFT", new_y="NEXT")
    if billing.authorised_signatory:
        pdf.set_x(x)
        pdf.set_text_color(*MUTED)
        pdf.cell(width, 4, "Authorised signatory", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*INK)


def money_rows(doc, total_label):
    return [("Subtotal", inr(doc.subtotal), False), ("Discount", f"− {inr(doc.discount_amount)}", False),
            ("Taxable value", inr(doc.subtotal - doc.discount_amount), False), ("GST", inr(doc.gst_amount), False),
            (total_label, inr(doc.grand_total), True)]


def quotation_pdf(q):
    company, billing = CompanySettings.load(), BillingSettings.load()
    pdf = DocumentPDF(company)
    pdf.set_title(f"Quotation {q.quotation_number}")
    pdf.add_page()
    header(pdf, company, "QUOTATION", [("Quotation no.", q.quotation_number), ("Date", f"{q.quotation_date:%d %b %Y}"),
                                       ("Valid until", f"{q.valid_until:%d %b %Y}")])
    party_block(pdf, q)
    items_table(pdf, q)
    totals_block(pdf, money_rows(q, "Grand total"))
    text_section(pdf, "Payment terms", q.payment_terms)
    text_section(pdf, "Delivery terms", q.delivery_terms)
    text_section(pdf, "Notes", q.notes)
    text_section(pdf, "Terms & conditions", q.terms_conditions)
    signature(pdf, company, billing)
    return bytes(pdf.output())


def invoice_pdf(inv):
    company, billing = CompanySettings.load(), BillingSettings.load()
    pdf = DocumentPDF(company)
    pdf.set_title(f"Invoice {inv.invoice_number}")
    pdf.add_page()
    meta = [("Invoice no.", inv.invoice_number), ("Invoice date", f"{inv.invoice_date:%d %b %Y}")]
    if inv.due_date:
        meta.append(("Due date", f"{inv.due_date:%d %b %Y}"))
    if inv.sales_order_id:
        meta.append(("Sales order", inv.sales_order.order_number))
    if inv.status == inv.Status.CANCELLED:
        meta.append(("Status", "CANCELLED"))
    header(pdf, company, "TAX INVOICE" if company.gstin else "INVOICE", meta)
    party_block(pdf, inv)
    items_table(pdf, inv)
    rows = money_rows(inv, "Invoice total")
    if inv.credited_amount:
        rows.append(("Credited (returns)", f"− {inr(inv.credited_amount)}", False))
    if inv.amount_paid:
        rows.append(("Paid", f"− {inr(inv.amount_paid)}", False))
    if inv.status != inv.Status.CANCELLED:
        rows.append(("Balance due", inr(inv.balance), True))
    totals_block(pdf, rows)
    text_section(pdf, "Payment terms", inv.payment_terms)
    bank = [f"{label}: {value}" for label, value in (("Bank", billing.bank_name), ("Account name", billing.bank_account_name),
                                                    ("Account no.", billing.bank_account_number), ("IFSC", billing.bank_ifsc),
                                                    ("UPI", billing.upi_id)) if value]
    text_section(pdf, "Bank details", "\n".join(bank))
    text_section(pdf, "Notes", inv.notes)
    text_section(pdf, "Terms & conditions", inv.terms_conditions)
    signature(pdf, company, billing)
    return bytes(pdf.output())
