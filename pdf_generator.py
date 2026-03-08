from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    KeepTogether,
    PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def currency(value: float) -> str:
    return f"${value:,.2f}"


def get_branch_footer(settings: dict, branch_id: str) -> dict:
    branches = settings.get("branches", [])
    branch = next((b for b in branches if str(b.get("branch_id")) == str(branch_id)), None)

    if not branch and branches:
        branch = branches[0]

    if not branch:
        return {
            "tagline": "INNOVATIVE PUMPING SOLUTIONS • SUPPLY CHAIN SERVICES • SERVICE CENTERS",
            "address": "",
            "phone_fax": "",
        }

    address_parts = [
        branch.get("address", "").strip(),
        ", ".join(filter(None, [
            branch.get("city", "").strip(),
            branch.get("state", "").strip(),
            branch.get("zip", "").strip(),
        ])).strip(", "),
    ]
    address_line = " • ".join(part for part in address_parts if part)

    phone_fax_parts = []
    if branch.get("phone"):
        phone_fax_parts.append(f"PHONE: {branch['phone']}")
    if branch.get("fax"):
        phone_fax_parts.append(f"FAX: {branch['fax']}")

    return {
        "tagline": branch.get("tagline", "INNOVATIVE PUMPING SOLUTIONS • SUPPLY CHAIN SERVICES • SERVICE CENTERS"),
        "address": address_line,
        "phone_fax": " • ".join(phone_fax_parts),
    }


def draw_page_header(canvas, doc, logo_path: Path | None = None):
    canvas.saveState()

    page_width, page_height = LETTER

    if logo_path and logo_path.exists():
        try:
            desired_width = 1.55 * inch
            max_height = 0.55 * inch
            img_width, img_height = 500, 200
            aspect = img_height / img_width
            draw_width = desired_width
            draw_height = desired_width * aspect

            if draw_height > max_height:
                draw_height = max_height
                draw_width = draw_height / aspect

            canvas.drawImage(
                str(logo_path),
                doc.leftMargin,
                page_height - 0.93 * inch,
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    canvas.setFont("Helvetica-Bold", 10)
    canvas.setFillColor(colors.HexColor("#00508f"))
    canvas.drawRightString(
        page_width - doc.rightMargin,
        page_height - 0.75 * inch,
        "THE INDUSTRIAL DISTRIBUTION EXPERTS",
    )

    canvas.restoreState()


def draw_quote_metadata(
    canvas,
    doc,
    quote: dict,
    sales_engineer_name: str,
    sales_engineer_phone: str,
    sales_engineer_email: str,
):
    page_width, page_height = LETTER
    right_x = page_width - doc.rightMargin - 0.40 * inch

    title_y = page_height - 1.25 * inch
    line_gap = 0.27 * inch

    canvas.saveState()
    canvas.setFillColor(colors.black)

    label_x = right_x - 1.05 * inch
    value_x = right_x - 0.95 * inch

    canvas.setFont("Times-Bold", 18)
    canvas.drawRightString(right_x, title_y, "Quotation")

    canvas.setFont("Times-Bold", 11)
    canvas.drawRightString(label_x, title_y - line_gap, "Quote #:")
    canvas.drawRightString(label_x, title_y - 2 * line_gap, "Quote Date:")
    canvas.drawRightString(label_x, title_y - 3 * line_gap, "Sales Engineer:")
    canvas.drawRightString(label_x, title_y - 4 * line_gap, "Direct Phone:")
    canvas.drawRightString(label_x, title_y - 5 * line_gap, "Direct Email:")

    canvas.setFont("Times-Roman", 11)
    canvas.drawString(value_x, title_y - line_gap, str(quote["quote_number"]))
    canvas.drawString(value_x, title_y - 2 * line_gap, str(quote["date_created"]))
    canvas.drawString(value_x, title_y - 3 * line_gap, sales_engineer_name)
    canvas.drawString(value_x, title_y - 4 * line_gap, sales_engineer_phone)
    canvas.drawString(value_x, title_y - 5 * line_gap, sales_engineer_email)

    canvas.restoreState()


def draw_footer(canvas, doc, footer_info: dict):
    canvas.saveState()

    page_width, _ = LETTER
    center_x = page_width / 2
    footer_y_bottom = 0.28 * inch

    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(colors.HexColor("#00508f"))
    canvas.drawCentredString(center_x, footer_y_bottom + 0.32 * inch, footer_info["tagline"])

    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.black)
    if footer_info["address"]:
        canvas.drawCentredString(center_x, footer_y_bottom + 0.14 * inch, footer_info["address"])
    if footer_info["phone_fax"]:
        canvas.drawCentredString(center_x, footer_y_bottom, footer_info["phone_fax"])

    canvas.restoreState()


def add_terms_and_conditions_page(story, styles_dict):
    tc_title_style = styles_dict["tc_title_style"]
    tc_section_style = styles_dict["tc_section_style"]
    tc_body_style = styles_dict["tc_body_style"]
    tc_sub_style = styles_dict["tc_sub_style"]

    story.append(PageBreak())
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph("Terms & Conditions", tc_title_style))
    story.append(Spacer(1, 0.06 * inch))

    def sec(title: str):
        story.append(Paragraph(title, tc_section_style))

    def body(text: str):
        story.append(Paragraph(text, tc_body_style))

    def sub(label: str, text: str):
        story.append(Paragraph(f"({label})&nbsp;&nbsp;&nbsp;&nbsp;{text}", tc_sub_style))

    sec("I.&nbsp;&nbsp;&nbsp;&nbsp;CONDITIONS")
    sub("a", 'No terms and conditions contained in any order placed with DXP ENTERPRISES, INC., herein referred to as “Company”, other than those stated herein shall be binding on Company.')
    sub("b", "All orders are subject to acceptance by an officer of Company.")

    sec("II.&nbsp;&nbsp;&nbsp;&nbsp;PRICES")
    body("All prices quoted herein will be subject to the prices in effect at time of shipment.")

    sec("III.&nbsp;&nbsp;&nbsp;&nbsp;TERMS OF PAYMENT")
    sub("a", "Payment Terms are NET cash thirty (30) days after shipment or notification that shipment is ready to be made. These terms apply to partial as well as complete shipments.")
    sub("b", "All orders subject to approval of credit.")

    sec("IV.&nbsp;&nbsp;&nbsp;&nbsp;STANDARD WARRANTY")
    sub("a", "The Company warrants its machinery, so far as the same is of its own manufacture, against defects in material and workmanship under normal use and service for which the equipment was designed for a period of one year after date of acceptance but not later than eighteen (18) months from date of shipment. The Company will warrant components or parts not manufactured by it to the same extent that the respective manufacture warrants such equipment and material.")
    sub("b", "This warranty does not obligate the Company to bear the cost of labor or transportation charges in connection with the replacement or repair of defective parts without approval by an officer of the Company prior to the time repairs are made. The obligation under this warranty may be limited to the repair or replacement of parts f.o.b. its factory provided that upon inspection at such point they shall be determined by the Company to have been defective in material or workmanship.")
    sub("c", "If the Company can agree that circumstances require the replacement or repair of defective parts on the jobsite, after a Company representative has determined that a warranty situation does exist, and that no revisions or alterations have been made to the equipment by others, the Company representative will implement the required repairs on an eight-hour straight time basis only.")
    sub("d", "Acceptance of the material from a common carrier constitutes a waiver of any claim against the Company for delay or damages in transit.")

    sec("V.&nbsp;&nbsp;&nbsp;&nbsp;SHIPMENT")
    sub("a", "Shipment quoted is effective as of proposal date and will be confirmed upon receipt of order, subject to availability of materials and production space. The Company shall not be held responsible for delays due to causes beyond the Company’s control such as strikes, riots, carrier delays, etc.")
    sub("b", "Should significant manufacturing changes or additions be made by the Purchaser after production has begun, shipping commitments may be extended at the Company’s discretion.")

    sec("VI.&nbsp;&nbsp;&nbsp;&nbsp;TAXES")
    body("The Purchaser shall pay to the Company, in addition to the purchase price, the amount of all Sales, Use, Privilege, Occupation, Excise, or other taxes, Federal, State, local or foreign which the Company is required to pay in connection with furnishing goods or services to the Purchaser.")

    sec("VII.&nbsp;&nbsp;&nbsp;&nbsp;INSTALLATION")
    body("Equipment shall be transported, installed and connected at Purchaser’s risk and expense. The Company may offer to furnish a service representative to assist in initial installation and start-up, which will be invoiced separately at our current published rates plus living and traveling expenses.")


def build_quote_pdf(
    quote: dict,
    pdf_path: Path,
    settings: dict,
    logo_path: Path | None = None,
):
    styles = getSampleStyleSheet()

    user_settings = settings.get("user", {})
    quote_settings = settings.get("quotes", {})
    sales_engineer_name = user_settings.get("sales_engineer_name", "")
    sales_engineer_phone = user_settings.get("sales_engineer_phone", "")
    sales_engineer_email = user_settings.get("sales_engineer_email", "")
    footer_info = get_branch_footer(settings, str(quote.get("branch_id", "")))

    if logo_path is None:
        static_logo = Path(__file__).resolve().parent / "static" / "img" / "dxp_logo.png"
        logo_path = static_logo if static_logo.exists() else None

    normal_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=11,
        leading=13,
        spaceAfter=2,
        alignment=TA_LEFT,
    )

    info_style = ParagraphStyle(
        "InfoStyle",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=11,
        leading=13,
        spaceAfter=0,
        alignment=TA_RIGHT,
    )

    section_heading_style = ParagraphStyle(
        "SectionHeading",
        parent=normal_style,
        fontName="Times-Bold",
        fontSize=11,
        leading=13,
        spaceAfter=3,
        spaceBefore=4,
    )

    small_style = ParagraphStyle(
        "Small",
        parent=normal_style,
        fontName="Times-Roman",
        fontSize=10,
        leading=12,
        spaceAfter=0,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=small_style,
        fontName="Times-Bold",
        fontSize=10,
        leading=11,
        alignment=TA_LEFT,
    )

    notes_heading_style = ParagraphStyle(
        "NotesHeading",
        parent=normal_style,
        fontName="Times-Roman",
        fontSize=11,
        leading=10.5,
        spaceBefore=2,
        spaceAfter=1,
    )

    notes_body_style = ParagraphStyle(
        "NotesBody",
        parent=normal_style,
        fontName="Times-Roman",
        fontSize=11,
        leading=11.5,
        spaceBefore=0.5,
        spaceAfter=0.8,
    )

    notes_bullet_style = ParagraphStyle(
        "NotesBullet",
        parent=notes_body_style,
        leftIndent=0.13 * inch,
        firstLineIndent=-0.09 * inch,
        bulletIndent=0.02 * inch,
        spaceAfter=0.5,
    )

    notes_closing_style = ParagraphStyle(
        "NotesClosing",
        parent=notes_body_style,
        fontName="Times-Roman",
        fontSize=11,
        leading=11.5,
        spaceAfter=0.5,
    )

    tc_title_style = ParagraphStyle(
        "TCTitle",
        parent=normal_style,
        fontName="Times-Bold",
        fontSize=16,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=4,
    )

    tc_section_style = ParagraphStyle(
        "TCSection",
        parent=normal_style,
        fontName="Times-Bold",
        fontSize=10.5,
        leading=12,
        spaceBefore=1.5,
        spaceAfter=0,
    )

    tc_body_style = ParagraphStyle(
        "TCBody",
        parent=normal_style,
        fontName="Times-Roman",
        fontSize=9,
        leading=10.5,
        leftIndent=0.36 * inch,
        spaceBefore=0,
        spaceAfter=0.5,
    )

    tc_sub_style = ParagraphStyle(
        "TCSub",
        parent=tc_body_style,
        leftIndent=0.36 * inch,
        firstLineIndent=0,
        spaceBefore=0,
        spaceAfter=0.5,
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=LETTER,
        leftMargin=0.50 * inch,
        rightMargin=0.50 * inch,
        topMargin=1.35 * inch,
        bottomMargin=0.95 * inch,
    )

    story = []
    story.append(Spacer(1, 0.62 * inch))

    customer_project_table = Table(
        [
            [Paragraph("<b>Customer:</b>", normal_style), Paragraph(quote["customer"], normal_style)],
            [Paragraph("<b>Project:</b>", normal_style), Paragraph(quote["project_description"], normal_style)],
        ],
        colWidths=[1.05 * inch, 6.55 * inch],
    )
    customer_project_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(customer_project_table)
    story.append(Spacer(1, 0.35 * inch))

    intro_text = quote_settings.get("default_cover_info_text", "")
    if intro_text:
        story.append(Paragraph(intro_text, normal_style))
        story.append(Spacer(1, 0.10 * inch))

    line_items_data = [[
        Paragraph("Item", table_header_style),
        Paragraph("Description", table_header_style),
        Paragraph("Qty", table_header_style),
        Paragraph("Unit Price", table_header_style),
        Paragraph("Ext. Price", table_header_style),
    ]]

    for item in quote["line_items"]:
        description_parts = []
        if item.get("item_description"):
            description_parts.append(item["item_description"])
        if item.get("item_long_description"):
            description_parts.append(item["item_long_description"])
        if item.get("lead_time"):
            description_parts.append(f"<i>Lead Time: {item['lead_time']}</i>")

        description_text = "<br/>".join(description_parts) if description_parts else ""

        line_items_data.append([
            Paragraph(item["item_name"] or "", small_style),
            Paragraph(description_text, small_style),
            Paragraph(str(item["quantity"]), small_style),
            Paragraph(currency(item["sell_price_each"]), small_style),
            Paragraph(currency(item["line_total"]), small_style),
        ])

    col_widths = [
        0.95 * inch,
        4.50 * inch,
        0.45 * inch,
        0.95 * inch,
        0.97 * inch,
    ]

    line_table = Table(line_items_data, colWidths=col_widths, repeatRows=1)
    line_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#d9e2f3")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Times-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.08 * inch))

    validity_text = quote_settings.get("default_quote_validity", "")
    if validity_text:
        story.append(Paragraph(validity_text, normal_style))
        story.append(Spacer(1, 0.06 * inch))

    total_table = Table(
        [[
            Paragraph("Quote Total", info_style),
            Paragraph(f"<b>{currency(quote['quote_total'])}</b>", info_style),
        ]],
        colWidths=[1.40 * inch, 1.10 * inch],
        hAlign="RIGHT",
    )
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)
    story.append(Spacer(1, 0.08 * inch))

    notes_block = []
    notes_block.append(Paragraph("Notes", section_heading_style))
    notes_block.append(Spacer(1, 0.01 * inch))

    def add_heading(text: str):
        notes_block.append(Paragraph(text, notes_heading_style))

    def add_bullet(text: str):
        notes_block.append(Paragraph(f"• {text}", notes_bullet_style))

    add_heading("Price")
    add_bullet("Payment Terms: Net 30")
    add_bullet("Pricing subject to change at time of order due to government imposed tariffs")
    notes_block.append(Spacer(1, 0.03 * inch))

    add_heading("Freight")
    add_bullet("Freight Terms: Prepaid and Add")
    add_bullet("Shipping Point and FOB point manufacturer’s factory")
    add_bullet("Freight, shipping and handling, rigging, export crating and loading/off loading is not included (unless otherwise noted)")
    notes_block.append(Spacer(1, 0.03 * inch))

    add_heading("Lead Time")
    add_bullet("Delivery: (See Above) Weeks After written acceptance of purchase order and upon full written release of equipment and manufacturing.")
    add_bullet("Deliveries quoted ARO are based on a two week turn-around of approved drawings (if applicable) from date of initial submittal. Any delays will postpone delivery.")
    add_bullet("Delivery is based upon acceptance of purchase order by seller and having full release to procure long lead items upon acceptance.")
    notes_block.append(Spacer(1, 0.03 * inch))

    add_heading("Confidentiality")
    add_bullet("This proposal, including attachments, is confidential and intended solely for use by the recipient to whom it is addressed and the end user noted herein. Do not copy, forward or disclose this proposal in whole or in part without permission from DXP Enterprises, Inc.")
    notes_block.append(Spacer(1, 0.04 * inch))

    for item in notes_block:
        story.append(item)

    signature_lines = quote_settings.get("default_signature_lines", [])
    closing_block = []
    for line in signature_lines:
        if line.strip():
            closing_block.append(Paragraph(line, notes_closing_style))
        else:
            closing_block.append(Spacer(1, 0.04 * inch))

    if closing_block:
        story.append(KeepTogether(closing_block))

    add_terms_and_conditions_page(
        story,
        {
            "tc_title_style": tc_title_style,
            "tc_section_style": tc_section_style,
            "tc_body_style": tc_body_style,
            "tc_sub_style": tc_sub_style,
        },
    )

    def first_page_callback(canvas, doc):
        draw_page_header(canvas, doc, logo_path)
        draw_quote_metadata(
            canvas,
            doc,
            quote,
            sales_engineer_name,
            sales_engineer_phone,
            sales_engineer_email,
        )
        draw_footer(canvas, doc, footer_info)

    def later_page_callback(canvas, doc):
        draw_page_header(canvas, doc, logo_path)
        draw_footer(canvas, doc, footer_info)

    doc.build(story, onFirstPage=first_page_callback, onLaterPages=later_page_callback)