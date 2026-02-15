"""Reporting service for PDF generation."""

import base64
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def generate_loan_book_pdf(applications: list) -> io.BytesIO:
    """Generate a PDF loan book report."""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("Zotta - Loan Book Report", styles["Title"]))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Normal"]))
        elements.append(Spacer(1, 0.5 * inch))

        # Table data
        data = [["Reference", "Status", "Requested", "Approved", "Rate", "Term"]]
        for app in applications:
            data.append([
                app.reference_number,
                app.status.value,
                f"TTD {float(app.amount_requested):,.2f}",
                f"TTD {float(app.amount_approved):,.2f}" if app.amount_approved else "-",
                f"{float(app.interest_rate):.1f}%" if app.interest_rate else "-",
                f"{app.term_months}m",
            ])

        if len(data) > 1:
            table = Table(data, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f7fafc")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(table)
        else:
            elements.append(Paragraph("No applications found.", styles["Normal"]))

        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.exception(f"Error in generate_loan_book_pdf: {e}")
        raise


# ── Consent & Contract PDF ────────────────────────────────


def _sig_image(data_url: str, width: float = 2.0 * inch, height: float = 0.6 * inch) -> Optional[Image]:
    """Convert a base64 data-URL (image/png) to a ReportLab Image flowable."""
    try:
        header, b64 = data_url.split(",", 1)
        raw = base64.b64decode(b64)
        buf = io.BytesIO(raw)
        return Image(buf, width=width, height=height)
    except Exception:
        return None


def generate_consent_pdf(
    *,
    lender_name: str,
    lender_address: str,
    applicant_name: str,
    applicant_address: str,
    national_id: str,
    reference_number: str,
    product_name: str,
    amount: float,
    term_months: int,
    monthly_payment: float,
    total_financed: float,
    downpayment: float,
    interest_rate: Optional[float],
    signature_data_url: str = "",
    signed_at: Optional[datetime] = None,
) -> io.BytesIO:
    """Generate a combined Hire Purchase Agreement and Consent PDF."""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            topMargin=0.6 * inch,
            bottomMargin=0.6 * inch,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("ConTitle", parent=styles["Title"], fontSize=14, spaceAfter=4, alignment=TA_CENTER)
        subtitle_style = ParagraphStyle("ConSubtitle", parent=styles["Normal"], fontSize=9, alignment=TA_CENTER,
                                         textColor=colors.HexColor("#555555"), spaceAfter=12)
        heading_style = ParagraphStyle("ConHeading", parent=styles["Heading2"], fontSize=12, spaceBefore=14, spaceAfter=6)
        body_style = ParagraphStyle("ConBody", parent=styles["Normal"], fontSize=10, leading=14, spaceAfter=6,
                                 alignment=TA_JUSTIFY)
        small_style = ParagraphStyle("ConSmall", parent=styles["Normal"], fontSize=9, leading=12, spaceAfter=4,
                                     alignment=TA_JUSTIFY, textColor=colors.HexColor("#333333"))
        label_style = ParagraphStyle("ConLabel", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666666"))

        elements: list = []
        signed_date_str = signed_at.strftime("%B %d, %Y") if signed_at else datetime.now().strftime("%B %d, %Y")
        rate_str = f"{interest_rate:.1f}%" if interest_rate else "As determined"
        total_repayment = monthly_payment * term_months if monthly_payment > 0 else amount
        total_interest = total_repayment - total_financed if total_repayment > total_financed else 0

        # ────────────────────────────────────────────────────
        # PART 1: HIRE PURCHASE AGREEMENT
        # ────────────────────────────────────────────────────
        elements.append(Paragraph("REPUBLIC OF TRINIDAD AND TOBAGO", subtitle_style))
        elements.append(Paragraph("HIRE PURCHASE AGREEMENT", title_style))
        elements.append(Paragraph(
            "THIS AGREEMENT IS SUBJECT TO VERIFICATION OF THE HIRER'S INFORMATION AND FINAL CREDIT APPROVAL",
            ParagraphStyle("Disclaimer", parent=small_style, alignment=TA_CENTER, textColor=colors.HexColor("#999999"), spaceAfter=16),
        ))

        elements.append(Paragraph(
            f'This Hire Purchase Agreement ("Agreement") is made and entered into on this '
            f'{signed_date_str}, by and between:',
            body_style,
        ))

        elements.append(Paragraph(
            f'<b>Owner:</b> {lender_name}, having its principal place of business at '
            f'{lender_address} (hereinafter referred to as the "Owner").',
            body_style,
        ))
        elements.append(Paragraph(
            f'<b>Hirer:</b> {applicant_name}, residing at {applicant_address} '
            f'(hereinafter referred to as the "Hirer").',
            body_style,
        ))

        elements.append(Spacer(1, 6))

        # Schedule
        elements.append(Paragraph("Schedule of Hire Purchase", heading_style))
        sched_data = [
            ["Description", "Value"],
            ["Product / Goods", product_name],
            ["Cash Price (Purchase Amount)", f"TTD {amount:,.2f}"],
            ["Down Payment", f"TTD {downpayment:,.2f}"],
            ["Total Amount Financed", f"TTD {total_financed:,.2f}"],
            ["Interest Rate (per annum)", rate_str],
            ["Term", f"{term_months} months"],
            ["Monthly Instalment", f"TTD {monthly_payment:,.2f}"],
            ["Total Repayment", f"TTD {total_repayment:,.2f}"],
            ["Total Interest Charges", f"TTD {total_interest:,.2f}"],
        ]
        sched_table = Table(sched_data, colWidths=[3.0 * inch, 3.5 * inch])
        sched_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(sched_table)
        elements.append(Spacer(1, 8))

        # Terms
        elements.append(Paragraph("Terms and Conditions", heading_style))
        terms = [
            "The Hirer agrees to pay the Owner the Total Repayment in equal monthly instalments as set out above.",
            "Title to the goods shall remain with the Owner until the Total Repayment has been paid in full.",
            "The Hirer shall keep the goods in good condition and shall not sell, pledge, or otherwise dispose of the goods.",
            "If the Hirer defaults on any instalment for 14 days or more, the Owner may demand immediate payment of the entire outstanding balance.",
            "Late payments may incur additional fees as per the Owner's fee schedule.",
            "The Hirer may terminate this agreement at any time by returning the goods and paying all amounts due.",
            "This Agreement shall be governed by the laws of the Republic of Trinidad and Tobago.",
            "The Owner reserves the right to transfer or assign this agreement to third parties.",
        ]
        for i, term in enumerate(terms, 1):
            elements.append(Paragraph(f"{i}. {term}", small_style))

        elements.append(Spacer(1, 16))

        # ────────────────────────────────────────────────────
        # PART 2: CREDIT APPLICATION CONSENT AND INDEMNITY
        # ────────────────────────────────────────────────────
        elements.append(Paragraph("CREDIT APPLICATION CONSENT AND INDEMNITY", title_style))
        elements.append(Spacer(1, 4))

        # From / Reference header
        hdr_data = [
            [Paragraph(f"<b>From:</b> {applicant_name}", body_style),
             Paragraph(f"<b>Reference #</b> {reference_number}", body_style)],
        ]
        hdr_table = Table(hdr_data, colWidths=[3.5 * inch, 3.0 * inch])
        hdr_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(hdr_table)
        elements.append(Spacer(1, 6))

        elements.append(Paragraph(f"<b>To: {lender_name}</b>", body_style))
        elements.append(Spacer(1, 8))

        elements.append(Paragraph(
            'I confirm that all the information I provided is true and correct and I understand '
        'that it will be used to check my credit worthiness and my credit history. I also '
            f'confirm that I have not withheld any information that may impact {lender_name} making '
            'an informed decision.',
            body_style,
        ))
        elements.append(Spacer(1, 6))

        elements.append(Paragraph(f"I also provide my consent for {lender_name} to:", body_style))
        consent_items = [
            "Access my credit information from banks and credit reporting bureaus to assess my "
            "credit worthiness and to related business purposes tied to my application.",
            "Share my credit information with credit reporting bureaus to update my records or "
            "for other legitimate business purposes.",
        ]
        for i, item in enumerate(consent_items, 1):
            elements.append(Paragraph(f"&nbsp;&nbsp;&nbsp;&nbsp;{i})&nbsp;&nbsp;{item}", small_style))

        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            f"I understand that {lender_name} needs this access to effectively provide its services.",
            body_style,
        ))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(
            f"I also agree to indemnify {lender_name}, its directors and staff from any and all claims or "
            "costs arising out of or in connection with the lawful access, disclosure or use of my "
            "credit information as authorized by this consent. This consent remains valid until "
            "revoked by me in writing.",
            body_style,
        ))
        elements.append(Spacer(1, 20))

        # ── Signature block ───────────────────────────────
        sig_img = _sig_image(signature_data_url) if signature_data_url else None
        if sig_img:
            sig_cell = sig_img
        elif signature_data_url:
            sig_cell = Paragraph("(signature on file)", body_style)
        else:
            sig_cell = Paragraph("&nbsp;", body_style)  # blank line for manual signing

        sig_data = [
            [Paragraph("<b>Customer's Signature:</b>", label_style), sig_cell],
            [Paragraph("<b>ID #</b>", label_style),
             Paragraph(national_id or "—", body_style)],
            [Paragraph("<b>Date:</b>", label_style),
             Paragraph(signed_date_str if signed_at else "____________________", body_style)],
        ]
        sig_table = Table(sig_data, colWidths=[2.0 * inch, 4.5 * inch])
        sig_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LINEBELOW", (1, 0), (1, 0), 0.5, colors.black),
            ("LINEBELOW", (1, 1), (1, 1), 0.5, colors.black),
            ("LINEBELOW", (1, 2), (1, 2), 0.5, colors.black),
        ]))
        elements.append(sig_table)

        doc.build(elements)
        buffer.seek(0)
        return buffer
    except Exception as e:
        logger.exception(f"Error in generate_consent_pdf: {e}")
        raise
