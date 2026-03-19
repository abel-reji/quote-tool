from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa
from pypdf import PdfWriter
import io
import os
import sys

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

def convert_html_to_pdf(html_string: str) -> io.BytesIO:
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(
        src=html_string,
        dest=result
    )
    if pisa_status.err:
        raise Exception(f"Failed to generate PDF from HTML")
    result.seek(0)
    return result

def build_quote_pdf(
    quote: dict,
    pdf_path: Path,
    settings: dict,
    logo_path: Path | None = None,
):
    if getattr(sys, 'frozen', False):
        BUNDLE_DIR = Path(sys._MEIPASS)
        EXE_DIR = Path(sys.executable).parent
        DATA_DIR = EXE_DIR / "data"
        use_external_assets = os.environ.get("QUOTE_TOOL_USE_EXTERNAL_ASSETS") == "1"
        # Prefer bundled templates unless external assets are explicitly enabled.
        external_templates = EXE_DIR / "templates"
        template_dir = str(external_templates) if use_external_assets and external_templates.exists() else str(BUNDLE_DIR / "templates")
    else:
        BUNDLE_DIR = Path(__file__).resolve().parent
        DATA_DIR = BUNDLE_DIR / "data"
        template_dir = str(BUNDLE_DIR / "templates")

    env = FileSystemLoader(template_dir)
    # auto_reload=True ensures Jinja re-reads the file if it changes on disk
    jinja_env = Environment(loader=env, auto_reload=True)

    user_settings = settings.get("user", {})
    quote_settings = settings.get("quotes", {})
    footer_info = get_branch_footer(settings, str(quote.get("branch_id", "")))

    if logo_path is None:
        static_logo = BUNDLE_DIR / "static" / "img" / "dxp_logo.png"
        logo_path = static_logo if static_logo.exists() else None

    # Load and render quote HTML
    quote_template = jinja_env.get_template("quote_pdf.html")
    quote_html = quote_template.render(
        quote=quote,
        sales_engineer_name=user_settings.get("sales_engineer_name", ""),
        sales_engineer_phone=user_settings.get("sales_engineer_phone", ""),
        sales_engineer_email=user_settings.get("sales_engineer_email", ""),
        logo_path=str(logo_path.as_posix()) if logo_path else None,
        footer_info=footer_info,
        intro_text=quote_settings.get("default_cover_info_text", ""),
        validity_text=quote_settings.get("default_quote_validity", ""),
        signature_lines=quote_settings.get("default_signature_lines", [])
    )

    # Render T&Cs HTML
    tc_template = jinja_env.get_template("tc_pdf.html")
    tc_html = tc_template.render(
        logo_path=str(logo_path.as_posix()) if logo_path else None,
        footer_info=footer_info
    )

    # Convert HTML to PDFs
    quote_pdf_io = convert_html_to_pdf(quote_html)
    tc_pdf_io = convert_html_to_pdf(tc_html)

    # Merge Pdfs: Main -> Attachments -> T&Cs
    merger = PdfWriter()
    merger.append(quote_pdf_io)

    # Attachments
    attachments = quote.get("attachments", [])
    upload_dir = DATA_DIR / "uploads" / quote["quote_number"]
    for attachment in attachments:
        attachment_path = upload_dir / attachment
        if attachment_path.exists():
            merger.append(str(attachment_path))

    # T&Cs
    merger.append(tc_pdf_io)

    merger.write(str(pdf_path))
    merger.close()
