#!/usr/bin/env python3
"""Generate a realistic Trinidad & Tobago bank statement PDF for testing.

Produces a Republic Bank-style statement with the same transaction data
as bank_statement_ttd_good.csv, laid out as a proper bank document.
"""

import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Transaction data (matches bank_statement_ttd_good.csv) ─────────────────

TRANSACTIONS = [
    ("01 Oct 2025", "Opening Balance", "", "", "12,450.00"),
    ("01 Oct 2025", "SALARY - PETROTRIN ENERGY LTD", "", "8,500.00", "20,950.00"),
    ("02 Oct 2025", "ATM WITHDRAWAL - REPUBLIC BANK CHAGUANAS", "500.00", "", "20,450.00"),
    ("03 Oct 2025", "TSTT MOBILE TOP-UP", "150.00", "", "20,300.00"),
    ("04 Oct 2025", "MASSY STORES - TRINCITY MALL", "387.50", "", "19,912.50"),
    ("05 Oct 2025", "WASA WATER BILL - DIRECT DEBIT", "285.00", "", "19,627.50"),
    ("06 Oct 2025", "T&TEC ELECTRICITY - DIRECT DEBIT", "420.00", "", "19,207.50"),
    ("07 Oct 2025", "TRANSFER TO SAVINGS - SCOTIABANK TT", "", "0.00", "19,207.50"),
    ("08 Oct 2025", "PENNYWISE COSMETICS", "75.00", "", "19,132.50"),
    ("10 Oct 2025", "HOUSING DEV CORP - RENT", "2,800.00", "", "16,332.50"),
    ("12 Oct 2025", "JTA SUPERMARKET - PORT OF SPAIN", "245.00", "", "16,087.50"),
    ("14 Oct 2025", "BMOBILE DATA PLAN", "120.00", "", "15,967.50"),
    ("15 Oct 2025", "MAXI TAXI - PBR ROUTE", "50.00", "", "15,917.50"),
    ("17 Oct 2025", "RITUALS COFFEE HOUSE", "65.00", "", "15,852.50"),
    ("18 Oct 2025", "MOVIE TOWNE INVADERS BAY", "180.00", "", "15,672.50"),
    ("20 Oct 2025", "GUARDIAN LIFE INS PREMIUM", "350.00", "", "15,322.50"),
    ("22 Oct 2025", "ATM WITHDRAWAL - FCB ARIMA", "300.00", "", "15,022.50"),
    ("25 Oct 2025", "POS PARKING METER", "15.00", "", "15,007.50"),
    ("27 Oct 2025", "MEMBERS ONLY MARAVAL", "320.00", "", "14,687.50"),
    ("28 Oct 2025", "SAGICOR HEALTH PREMIUM", "275.00", "", "14,412.50"),
    ("30 Oct 2025", "DIGICEL POSTPAID BILL", "189.00", "", "14,223.50"),
    ("31 Oct 2025", "INTEREST CREDIT", "", "2.35", "14,225.85"),
    ("01 Nov 2025", "SALARY - PETROTRIN ENERGY LTD", "", "8,500.00", "22,725.85"),
    ("02 Nov 2025", "ATM WITHDRAWAL - RBC SANGRE GRANDE", "600.00", "", "22,125.85"),
    ("03 Nov 2025", "MASSY STORES - GULF CITY MALL", "412.00", "", "21,713.85"),
    ("05 Nov 2025", "WASA WATER BILL - DIRECT DEBIT", "285.00", "", "21,428.85"),
    ("06 Nov 2025", "T&TEC ELECTRICITY - DIRECT DEBIT", "395.00", "", "21,033.85"),
    ("07 Nov 2025", "PAN TRINBAGO EVENT TICKETS", "200.00", "", "20,833.85"),
    ("08 Nov 2025", "EXCELLENT STORES - SAN FERNANDO", "156.00", "", "20,677.85"),
    ("10 Nov 2025", "HOUSING DEV CORP - RENT", "2,800.00", "", "17,877.85"),
    ("12 Nov 2025", "PRICESMART CHAGUANAS", "680.00", "", "17,197.85"),
    ("14 Nov 2025", "BPTT FUEL STATION - COUVA", "250.00", "", "16,947.85"),
    ("15 Nov 2025", "MAXI TAXI - PBR ROUTE", "50.00", "", "16,897.85"),
    ("16 Nov 2025", "DOUBLES VENDOR", "20.00", "", "16,877.85"),
    ("18 Nov 2025", "SCOTIABANK TT - LOAN REPAYMENT", "1,200.00", "", "15,677.85"),
    ("20 Nov 2025", "GUARDIAN LIFE INS PREMIUM", "350.00", "", "15,327.85"),
    ("22 Nov 2025", "KFC INDEPENDENCE SQUARE", "85.00", "", "15,242.85"),
    ("24 Nov 2025", "CARIBBEAN CINEMAS", "150.00", "", "15,092.85"),
    ("25 Nov 2025", "COURTS MEGASTORE - HIRE PURCHASE", "450.00", "", "14,642.85"),
    ("27 Nov 2025", "SAGICOR HEALTH PREMIUM", "275.00", "", "14,367.85"),
    ("28 Nov 2025", "TRANSFER TO SAVINGS - RBC", "500.00", "", "13,867.85"),
    ("30 Nov 2025", "DIGICEL POSTPAID BILL", "189.00", "", "13,678.85"),
    ("30 Nov 2025", "INTEREST CREDIT", "", "2.15", "13,681.00"),
    ("01 Dec 2025", "SALARY - PETROTRIN ENERGY LTD", "", "8,500.00", "22,181.00"),
    ("01 Dec 2025", "CHRISTMAS BONUS - PETROTRIN", "", "4,250.00", "26,431.00"),
    ("02 Dec 2025", "ATM WITHDRAWAL - REPUBLIC BANK TUNAPUNA", "800.00", "", "25,631.00"),
    ("03 Dec 2025", "MASSY STORES - TRINCITY MALL", "525.00", "", "25,106.00"),
    ("05 Dec 2025", "WASA WATER BILL - DIRECT DEBIT", "285.00", "", "24,821.00"),
    ("06 Dec 2025", "T&TEC ELECTRICITY - DIRECT DEBIT", "480.00", "", "24,341.00"),
    ("08 Dec 2025", "LONG CIRCULAR MALL - XMAS SHOPPING", "1,200.00", "", "23,141.00"),
    ("10 Dec 2025", "HOUSING DEV CORP - RENT", "2,800.00", "", "20,341.00"),
    ("12 Dec 2025", "PRICESMART CHAGUANAS", "950.00", "", "19,391.00"),
    ("14 Dec 2025", "BPTT FUEL STATION - CUREPE", "280.00", "", "19,111.00"),
    ("15 Dec 2025", "MAXI TAXI - PBR ROUTE", "50.00", "", "19,061.00"),
    ("16 Dec 2025", "SCOTIABANK TT - LOAN REPAYMENT", "1,200.00", "", "17,861.00"),
    ("18 Dec 2025", "GUARDIAN LIFE INS PREMIUM", "350.00", "", "17,511.00"),
    ("20 Dec 2025", "EXCELLENT STORES XMAS GIFTS", "480.00", "", "17,031.00"),
    ("22 Dec 2025", "SAGICOR HEALTH PREMIUM", "275.00", "", "16,756.00"),
    ("24 Dec 2025", "HI-LO FOOD STORES - CHRISTMAS GROCERIES", "750.00", "", "16,006.00"),
    ("25 Dec 2025", "CHURCH DONATION", "100.00", "", "15,906.00"),
    ("28 Dec 2025", "TRANSFER TO SAVINGS - RBC", "1,000.00", "", "14,906.00"),
    ("30 Dec 2025", "DIGICEL POSTPAID BILL", "189.00", "", "14,717.00"),
    ("31 Dec 2025", "INTEREST CREDIT", "", "3.10", "14,720.10"),
]


def build_pdf(output_path: str) -> None:
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )

    styles = getSampleStyleSheet()
    elements: list = []

    # ── Custom styles ──────────────────────────────────────────────────
    bank_name_style = ParagraphStyle(
        "BankName",
        parent=styles["Title"],
        fontSize=18,
        textColor=colors.HexColor("#003366"),
        spaceAfter=2,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#666666"),
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#003366"),
        spaceBefore=8,
        spaceAfter=4,
    )
    normal = ParagraphStyle(
        "NormalCustom",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
    )
    bold_style = ParagraphStyle(
        "BoldCustom",
        parent=normal,
        fontName="Helvetica-Bold",
    )
    right_style = ParagraphStyle(
        "RightAligned",
        parent=normal,
        alignment=TA_RIGHT,
    )

    # ── Bank header ────────────────────────────────────────────────────
    elements.append(Paragraph("Republic Bank Limited", bank_name_style))
    elements.append(Paragraph(
        "Head Office: 9-17 Park Street, Port of Spain, Trinidad and Tobago, W.I.",
        subtitle_style,
    ))
    elements.append(Paragraph(
        "Tel: (868) 623-1056  |  Fax: (868) 624-1323  |  www.republicbnk.com  |  Swift: RABORTT",
        subtitle_style,
    ))
    elements.append(HRFlowable(
        width="100%", thickness=2, color=colors.HexColor("#003366"), spaceAfter=10,
    ))

    # ── Statement title ────────────────────────────────────────────────
    elements.append(Paragraph("STATEMENT OF ACCOUNT", heading_style))
    elements.append(Spacer(1, 4))

    # ── Account info table ─────────────────────────────────────────────
    info_data = [
        [
            Paragraph("<b>Account Holder:</b>", normal),
            Paragraph("MARCUS A. MOHAMMED", normal),
            Paragraph("<b>Branch:</b>", normal),
            Paragraph("Chaguanas", normal),
        ],
        [
            Paragraph("<b>Account Number:</b>", normal),
            Paragraph("160-1198-7745-02", normal),
            Paragraph("<b>Account Type:</b>", normal),
            Paragraph("Chequing Savings", normal),
        ],
        [
            Paragraph("<b>Currency:</b>", normal),
            Paragraph("Trinidad & Tobago Dollar (TTD)", normal),
            Paragraph("<b>Statement Period:</b>", normal),
            Paragraph("01 October 2025 – 31 December 2025", normal),
        ],
        [
            Paragraph("<b>Address:</b>", normal),
            Paragraph("42 Southern Main Road, Cunupia, Trinidad, W.I.", normal),
            Paragraph("<b>Page:</b>", normal),
            Paragraph("1 of 1", normal),
        ],
    ]
    info_table = Table(info_data, colWidths=[1.3 * inch, 2.3 * inch, 1.2 * inch, 2.0 * inch])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(
        width="100%", thickness=1, color=colors.HexColor("#cccccc"), spaceAfter=6,
    ))

    # ── Transaction table ──────────────────────────────────────────────
    elements.append(Paragraph("Transaction Details", heading_style))

    header = ["Date", "Description", "Debit (TTD)", "Credit (TTD)", "Balance (TTD)"]
    table_data = [header] + list(TRANSACTIONS)

    col_widths = [1.0 * inch, 3.0 * inch, 0.95 * inch, 0.95 * inch, 1.0 * inch]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    txn_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003366")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 0), (-1, 0), 5),
        # Body
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
        # Alignment
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("ALIGN", (0, 0), (1, -1), "LEFT"),
        # Grid
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.HexColor("#003366")),
        ("LINEBELOW", (0, -1), (-1, -1), 1, colors.HexColor("#003366")),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.HexColor("#e0e0e0")),
        # Alternating row shading
        *[
            ("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f8fc"))
            for i in range(2, len(table_data), 2)
        ],
    ]))
    elements.append(txn_table)
    elements.append(Spacer(1, 12))

    # ── Summary footer ─────────────────────────────────────────────────
    elements.append(HRFlowable(
        width="100%", thickness=1, color=colors.HexColor("#cccccc"), spaceAfter=8,
    ))
    summary_data = [
        ["Opening Balance (01 Oct 2025):", "TTD 12,450.00"],
        ["Total Credits:", "TTD 29,757.60"],
        ["Total Debits:", "TTD 27,487.50"],
        ["Closing Balance (31 Dec 2025):", "TTD 14,720.10"],
    ]
    summary_table = Table(summary_data, colWidths=[4.5 * inch, 2.0 * inch])
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.HexColor("#003366")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # ── Disclaimer ─────────────────────────────────────────────────────
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=7,
        textColor=colors.HexColor("#999999"),
        leading=9,
    )
    elements.append(Paragraph(
        "This statement has been computer-generated and does not require a signature. "
        "Please examine the entries carefully. If no discrepancy is reported within "
        "14 days, the account will be considered correct. Republic Bank Limited is "
        "regulated by the Central Bank of Trinidad and Tobago.",
        disclaimer_style,
    ))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        "Republic Bank Limited  •  Registered in the Republic of Trinidad and Tobago  •  "
        "Company No. 10025",
        disclaimer_style,
    ))

    doc.build(elements)
    print(f"PDF created: {output_path}")


if __name__ == "__main__":
    output = os.path.join(OUTPUT_DIR, "bank_statement_ttd_good.pdf")
    build_pdf(output)
