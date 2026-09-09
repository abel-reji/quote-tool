from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
from datetime import datetime
from sqlalchemy import text
import json
import csv
import re
import sys
import os
import shutil
import math
import tempfile
import io
from copy import deepcopy
from quote_pricing import calculate_item
from storage_lock import install_storage_lock
from markupsafe import escape
from storage_paths import private_child
from web_security import load_web_config, install_web_security

from pdf_generator import build_quote_pdf


APP_FOLDER_NAME = "Quote Tool"
WEB_CONFIG = load_web_config()


def get_local_appdata_root() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / APP_FOLDER_NAME
    return Path.home() / "AppData" / "Local" / APP_FOLDER_NAME


if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).parent
    use_external_assets = os.environ.get("QUOTE_TOOL_USE_EXTERNAL_ASSETS") == "1"

    # Persistent app data now lives in Local AppData, not beside the EXE
    APPDATA_ROOT = get_local_appdata_root()
    DATA_DIR = APPDATA_ROOT / "data"
    OUTPUT_DIR = APPDATA_ROOT / "output"

    # Legacy location used by previous builds
    LEGACY_DATA_DIR = EXE_DIR / "data"
    LEGACY_OUTPUT_DIR = EXE_DIR / "output"

    # Prefer bundled assets so stale files beside the EXE do not override new builds.
    # External assets can still be used explicitly by setting QUOTE_TOOL_USE_EXTERNAL_ASSETS=1.
    EXTERNAL_TEMPLATES = EXE_DIR / "templates"
    TEMPLATE_PATH = str(EXTERNAL_TEMPLATES) if use_external_assets and EXTERNAL_TEMPLATES.exists() else str(BUNDLE_DIR / "templates")

    EXTERNAL_STATIC = EXE_DIR / "static"
    STATIC_PATH = str(EXTERNAL_STATIC) if use_external_assets and EXTERNAL_STATIC.exists() else str(BUNDLE_DIR / "static")
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BUNDLE_DIR / "data"
    OUTPUT_DIR = BUNDLE_DIR / "output"
    LEGACY_DATA_DIR = DATA_DIR
    LEGACY_OUTPUT_DIR = OUTPUT_DIR
    TEMPLATE_PATH = str(BUNDLE_DIR / "templates")
    STATIC_PATH = str(BUNDLE_DIR / "static")

if WEB_CONFIG:
    DATA_DIR = WEB_CONFIG["storage_root"] / "data"
    OUTPUT_DIR = WEB_CONFIG["storage_root"] / "output"
elif os.environ.get("QUOTE_TOOL_STORAGE_ROOT"):
    # Explicit isolated storage also makes desktop regression tests safe.
    storage_root = Path(os.environ["QUOTE_TOOL_STORAGE_ROOT"]).resolve()
    DATA_DIR, OUTPUT_DIR = storage_root / "data", storage_root / "output"

app = Flask(__name__, template_folder=TEMPLATE_PATH, static_folder=STATIC_PATH)
install_web_security(app, WEB_CONFIG)

QUOTES_DIR = DATA_DIR / "quotes"
CUSTOMERS_FILE = DATA_DIR / "customers.json"
SETTINGS_FILE = DATA_DIR / "settings.json"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_FILE = DATA_DIR / "quotes.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
QUOTES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
install_storage_lock(app, DATA_DIR.parent)


def migrate_legacy_storage_if_needed():
    """
    On the first run of the rebuilt EXE, move persistent data from the old
    EXE-adjacent /data folder into Local AppData.
    """
    if WEB_CONFIG or os.environ.get("QUOTE_TOOL_STORAGE_ROOT") or not getattr(sys, "frozen", False):
        return

    if not LEGACY_DATA_DIR.exists() or LEGACY_DATA_DIR.resolve() == DATA_DIR.resolve():
        return

    legacy_db = LEGACY_DATA_DIR / "quotes.db"
    legacy_settings = LEGACY_DATA_DIR / "settings.json"
    legacy_customers = LEGACY_DATA_DIR / "customers.json"
    legacy_uploads = LEGACY_DATA_DIR / "uploads"
    legacy_quotes_dir = LEGACY_DATA_DIR / "quotes"

    # Copy DB if the new DB does not yet exist
    if not DB_FILE.exists() and legacy_db.exists():
        shutil.copy2(legacy_db, DB_FILE)

    # Copy settings/customers if missing
    if not SETTINGS_FILE.exists() and legacy_settings.exists():
        shutil.copy2(legacy_settings, SETTINGS_FILE)

    if not CUSTOMERS_FILE.exists() and legacy_customers.exists():
        shutil.copy2(legacy_customers, CUSTOMERS_FILE)

    # Copy uploads folder if missing or empty
    if legacy_uploads.exists():
        if not UPLOAD_DIR.exists():
            shutil.copytree(legacy_uploads, UPLOAD_DIR)
        else:
            for item in legacy_uploads.iterdir():
                target = UPLOAD_DIR / item.name
                if item.is_dir():
                    if not target.exists():
                        shutil.copytree(item, target)
                else:
                    if not target.exists():
                        shutil.copy2(item, target)

    # Copy legacy JSON quote files for optional migration fallback
    if legacy_quotes_dir.exists():
        for item in legacy_quotes_dir.glob("*.json"):
            target = QUOTES_DIR / item.name
            if not target.exists():
                shutil.copy2(item, target)


migrate_legacy_storage_if_needed()

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_FILE}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class Quote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    entry_type = db.Column(db.String(20), default="app")
    branch_id = db.Column(db.String(50))
    date_created = db.Column(db.String(50))
    customer = db.Column(db.String(255))
    customer_contact = db.Column(db.String(255))
    customer_email = db.Column(db.String(255))
    project_description = db.Column(db.String(255))
    disposition = db.Column(db.String(50), default="pending")
    quote_total = db.Column(db.Float, default=0.0)

    line_items = db.relationship("LineItem", backref="quote", lazy=True, cascade="all, delete-orphan", order_by="LineItem.id")
    attachments = db.relationship("Attachment", backref="quote", lazy=True, cascade="all, delete-orphan", order_by="Attachment.id")

    def to_dict(self):
        return {
            "quote_number": self.quote_number,
            "entry_type": self.entry_type or "app",
            "branch_id": self.branch_id,
            "date_created": self.date_created,
            "customer": self.customer,
            "customer_contact": self.customer_contact,
            "customer_email": self.customer_email,
            "project_description": self.project_description,
            "disposition": self.disposition,
            "quote_total": self.quote_total,
            "line_items": [li.to_dict() for li in self.line_items],
            "attachments": [a.filename for a in self.attachments],
        }


class LineItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quote.id"), nullable=False)
    item_name = db.Column(db.String(255))
    item_description = db.Column(db.String(255))
    item_long_description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    net_cost_each = db.Column(db.Float, default=0.0)
    sell_price_each = db.Column(db.Float, default=0.0)
    gross_margin_percent = db.Column(db.Float, default=0.0)
    lead_time = db.Column(db.String(100))
    line_total = db.Column(db.Float, default=0.0)
    item_type = db.Column(db.String(20), nullable=False, default="single")
    components = db.Column(db.JSON, nullable=True)

    def to_dict(self):
        return {
            "item_name": self.item_name,
            "item_description": self.item_description,
            "item_long_description": self.item_long_description,
            "quantity": self.quantity,
            "net_cost_each": self.net_cost_each,
            "sell_price_each": self.sell_price_each,
            "gross_margin_percent": self.gross_margin_percent,
            "lead_time": self.lead_time,
            "line_total": self.line_total,
            "item_type": self.item_type or "single",
            "components": deepcopy(self.components or []),
        }


class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quote.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)


DEFAULT_SETTINGS = {
    "user": {
        "sales_engineer_name": "Abel Reji",
        "sales_engineer_phone": "(918) 703-7381",
        "sales_engineer_email": "Abel.Reji@dxpe.com",
        "default_branch_id": "325",
    },
    "branches": [
        {
            "branch_id": "325",
            "branch_name": "Tulsa",
            "address": "4951 S. Frontage Road",
            "city": "Tulsa",
            "state": "OK",
            "zip": "74107",
            "phone": "918-446-5515",
            "fax": "918-446-0338",
            "tagline": "INNOVATIVE PUMPING SOLUTIONS • SUPPLY CHAIN SERVICES • SERVICE CENTERS",
        },
        {
            "branch_id": "190",
            "branch_name": "Oklahoma City",
            "address": "1401 SE 29th St",
            "city": "Oklahoma City",
            "state": "OK",
            "zip": "73129",
            "phone": "405-670-4491",
            "fax": "405-670-2702",
            "tagline": "INNOVATIVE PUMPING SOLUTIONS • SUPPLY CHAIN SERVICES • SERVICE CENTERS",
        },
    ],
    "quotes": {
        "default_cover_info_text": (
            "DXP is pleased to offer you the following quote. "
            "Should you require additional information or if we can be of further service, "
            "please contact us at your convenience."
        ),
        "default_quote_validity": (
            "Customer to approve rated design point, materials of construction, and NPSH requirements. "
            "Quote is valid for 30 days."
        ),
        "default_signature_lines": [
            "Thank you for the opportunity,",
            "",
            "Abel Reji",
            "Sales Engineer",
            "918-703-7381",
            "Abel.Reji@dxpe.com",
        ],
    },
}


def deep_merge(defaults, incoming):
    if isinstance(defaults, dict) and isinstance(incoming, dict):
        merged = dict(defaults)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    return incoming


def ensure_settings_file():
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)


def load_settings() -> dict:
    ensure_settings_file()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        return deep_merge(DEFAULT_SETTINGS, loaded)
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict):
    atomic_json_write(SETTINGS_FILE, settings)


def atomic_json_write(path: Path, value):
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".quote-json-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def get_branch_ids(settings: dict) -> set[str]:
    return {
        str(branch.get("branch_id", "")).strip()
        for branch in settings.get("branches", [])
        if branch.get("branch_id")
    }


def validate_quote_number(value: str) -> tuple[str | None, str | None]:
    quote_number = str(value or "").strip()

    if not quote_number:
        return None, "Quote number is required."

    if len(quote_number) > 50:
        return None, "Quote number must be 50 characters or fewer."

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", quote_number):
        return None, "Quote number must start with a letter or number and contain only letters, numbers, hyphens, underscores, and periods."

    return quote_number, None


def validate_date_created(value: str) -> tuple[str | None, str | None]:
    date_created = str(value or "").strip()

    if not date_created:
        return None, "Date created is required."

    try:
        parsed = datetime.strptime(date_created, "%Y-%m-%d")
    except ValueError:
        return None, "Date created must be a valid date in YYYY-MM-DD format."

    return parsed.strftime("%Y-%m-%d"), None


def normalize_entry_type(value: str | None) -> str:
    return "p21" if str(value or "").strip().lower() == "p21" else "app"


@app.route("/")
def landing_page():
    return render_template("landing.html")


@app.route("/quote-tool")
def quote_tool():
    settings = load_settings()
    return render_template("index.html", edit_mode=False, quote=None, settings=settings, entry_mode="app")


@app.route("/p21-quote")
def p21_quote_tool():
    settings = load_settings()
    return render_template("index.html", edit_mode=False, quote=None, settings=settings, entry_mode="p21")


@app.route("/quotes/<quote_number>/edit")
def edit_quote_page(quote_number):
    quote = load_quote(quote_number)
    if not quote:
        return f"Quote file not found: {escape(quote_number)}", 404

    settings = load_settings()
    return render_template("index.html", edit_mode=True, quote=quote, settings=settings, entry_mode=quote.get("entry_type", "app"))


@app.route("/settings")
def settings_page():
    settings = load_settings()
    return render_template("settings.html", settings=settings)


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def get_sales_engineer_initials(settings: dict) -> str:
    name = str(settings.get("user", {}).get("sales_engineer_name", "")).strip()

    if not name:
        return "XX"

    parts = [part for part in name.split() if part]
    if len(parts) == 1:
        return parts[0][0].upper()

    return f"{parts[0][0]}{parts[-1][0]}".upper()


def generate_quote_number(branch_id: str, settings: dict) -> str:
    date_code = datetime.now().strftime("%y%m%d")
    initials = get_sales_engineer_initials(settings)

    pattern = re.compile(
        rf"^{re.escape(branch_id)}-{date_code}(\d+){re.escape(initials)}$",
        re.IGNORECASE,
    )

    max_sequence = 0
    existing_quotes = Quote.query.filter(Quote.quote_number.like(f"{branch_id}-{date_code}%")).all()

    for q in existing_quotes:
        match = pattern.match(q.quote_number)
        if match:
            sequence = int(match.group(1))
            if sequence > max_sequence:
                max_sequence = sequence

    daily_sequence = max_sequence + 1
    return f"{branch_id}-{date_code}{daily_sequence}{initials}"


def calculate_line_item(item: dict) -> dict:
    return calculate_item(item)


def load_customers() -> list:
    if not CUSTOMERS_FILE.exists():
        return []

    try:
        with open(CUSTOMERS_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return []


def save_customers(customers: list):
    atomic_json_write(CUSTOMERS_FILE, customers)


def add_customer_if_new(customer_name: str):
    customer_name = customer_name.strip()
    if not customer_name:
        return

    customers = load_customers()
    existing_lower = {c.lower() for c in customers}

    if customer_name.lower() not in existing_lower:
        customers.append(customer_name)
        customers.sort(key=str.lower)
        save_customers(customers)


def load_quote(quote_number: str):
    quote_obj = Quote.query.filter_by(quote_number=quote_number).first()
    if not quote_obj:
        return None
    return quote_obj.to_dict()


def delete_quote_data(quote_number: str):
    quote_obj = Quote.query.filter_by(quote_number=quote_number).first()
    if quote_obj:
        db.session.delete(quote_obj)
        db.session.commit()

        quote_upload_dir = private_child(UPLOAD_DIR, quote_number)
        if quote_upload_dir.exists():
            for f in quote_upload_dir.iterdir():
                f.unlink()
            quote_upload_dir.rmdir()
        return True
    return False


def build_quote_payload(data: dict, existing_quote_number: str | None = None) -> tuple[dict | None, str | None]:
    settings = load_settings()

    entry_type = normalize_entry_type(data.get("entry_type"))
    branch_id = str(data.get("branch_id", "")).strip()
    customer = str(data.get("customer", "")).strip()
    customer_contact = str(data.get("customer_contact", "")).strip()
    customer_email = str(data.get("customer_email", "")).strip()
    project_description = str(data.get("project_description", "")).strip()
    disposition = str(data.get("disposition", "pending")).strip().lower()
    line_items = data.get("line_items", [])
    attachments_from_form = data.get("attachments", [])

    valid_branch_ids = get_branch_ids(settings)
    if branch_id not in valid_branch_ids:
        return None, "A valid branch ID is required."

    if not customer:
        return None, "Customer is required."

    if not project_description:
        return None, "Project description is required."

    if disposition not in {"won", "lost", "pending"}:
        disposition = "pending"

    if not isinstance(line_items, list) or len(line_items) == 0:
        return None, "At least one line item is required."

    try:
        processed_line_items = [calculate_line_item(item) for item in line_items]
    except ValueError as e:
        return None, str(e)

    quote_total = round(sum(item["line_total"] for item in processed_line_items), 2)
    if quote_total > 1000000000:
        return None, "Quote amount is too large."

    if existing_quote_number:
        existing_quote_obj = Quote.query.filter_by(quote_number=existing_quote_number).first()
        if not existing_quote_obj:
            return None, f"Quote not found: {existing_quote_number}"

        entry_type = normalize_entry_type(data.get("entry_type", existing_quote_obj.entry_type or "app"))
        requested_quote_number = data.get("quote_number", existing_quote_number)
        quote_number, quote_number_error = validate_quote_number(requested_quote_number)
        if quote_number_error:
            return None, quote_number_error

        if quote_number != existing_quote_number:
            conflicting_quote = Quote.query.filter_by(quote_number=quote_number).first()
            if conflicting_quote:
                return None, f"Quote number already exists: {quote_number}"

        requested_date_created = data.get("date_created", existing_quote_obj.date_created or datetime.now().strftime("%Y-%m-%d"))
        date_created, date_created_error = validate_date_created(requested_date_created)
        if date_created_error:
            return None, date_created_error
        existing_attachments_db = [a.filename for a in existing_quote_obj.attachments]
        final_attachments = [name for name in existing_attachments_db if name in attachments_from_form]
    else:
        if entry_type == "p21":
            quote_number, quote_number_error = validate_quote_number(data.get("quote_number"))
            if quote_number_error:
                return None, quote_number_error

            conflicting_quote = Quote.query.filter_by(quote_number=quote_number).first()
            if conflicting_quote:
                return None, f"Quote number already exists: {quote_number}"

            date_created, date_created_error = validate_date_created(data.get("date_created"))
            if date_created_error:
                return None, date_created_error
        else:
            quote_number = generate_quote_number(branch_id, settings)
            date_created = datetime.now().strftime("%Y-%m-%d")
        final_attachments = []

    return {
        "quote_number": quote_number,
        "entry_type": entry_type,
        "branch_id": branch_id,
        "date_created": date_created,
        "customer": customer,
        "customer_contact": customer_contact,
        "customer_email": customer_email,
        "project_description": project_description,
        "disposition": disposition,
        "line_items": processed_line_items,
        "quote_total": quote_total,
        "attachments": final_attachments,
    }, None


def get_export_rows() -> list[dict]:
    rows = []
    quotes = Quote.query.order_by(Quote.date_created.desc(), Quote.quote_number.desc()).all()

    for quote in quotes:
        rows.append({
            "Quote Number": quote.quote_number,
            "Customer": quote.customer,
            "Project Description": quote.project_description,
            "Quote Total": quote.quote_total,
            "Disposition": quote.disposition or "",
            "Date Created": quote.date_created,
        })
    return rows


@app.route("/api/settings", methods=["GET"])
def get_settings():
    return jsonify({"status": "success", "settings": load_settings()})


@app.route("/api/settings", methods=["POST"])
def update_settings():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received."}), 400

        user = data.get("user", {})
        branches = data.get("branches", [])
        quotes = data.get("quotes", {})

        if not isinstance(user, dict):
            return jsonify({"status": "error", "message": "Invalid user settings."}), 400

        if not isinstance(branches, list) or len(branches) == 0:
            return jsonify({"status": "error", "message": "At least one branch is required."}), 400

        if not isinstance(quotes, dict):
            return jsonify({"status": "error", "message": "Invalid quote settings."}), 400

        cleaned_branches = []
        seen_branch_ids = set()

        for index, branch in enumerate(branches, start=1):
            if not isinstance(branch, dict):
                return jsonify({"status": "error", "message": f"Branch #{index} is invalid."}), 400

            branch_id = str(branch.get("branch_id", "")).strip()
            if not branch_id:
                return jsonify({"status": "error", "message": f"Branch #{index}: Branch ID is required."}), 400

            if branch_id in seen_branch_ids:
                return jsonify({"status": "error", "message": f"Duplicate branch ID found: {branch_id}"}), 400

            seen_branch_ids.add(branch_id)

            cleaned_branches.append({
                "branch_id": branch_id,
                "branch_name": str(branch.get("branch_name", "")).strip(),
                "address": str(branch.get("address", "")).strip(),
                "city": str(branch.get("city", "")).strip(),
                "state": str(branch.get("state", "")).strip(),
                "zip": str(branch.get("zip", "")).strip(),
                "phone": str(branch.get("phone", "")).strip(),
                "fax": str(branch.get("fax", "")).strip(),
                "tagline": str(branch.get("tagline", "")).strip(),
            })

        default_branch_id = str(user.get("default_branch_id", "")).strip()
        if default_branch_id not in seen_branch_ids:
            return jsonify({"status": "error", "message": "Default branch must match one of the configured branches."}), 400

        signature_lines = quotes.get("default_signature_lines", [])
        if isinstance(signature_lines, str):
            signature_lines = [line.rstrip() for line in signature_lines.splitlines()]
        elif not isinstance(signature_lines, list):
            signature_lines = []

        cleaned_settings = {
            "user": {
                "sales_engineer_name": str(user.get("sales_engineer_name", "")).strip(),
                "sales_engineer_phone": str(user.get("sales_engineer_phone", "")).strip(),
                "sales_engineer_email": str(user.get("sales_engineer_email", "")).strip(),
                "default_branch_id": default_branch_id,
            },
            "branches": cleaned_branches,
            "quotes": {
                "default_cover_info_text": str(quotes.get("default_cover_info_text", "")).strip(),
                "default_quote_validity": str(quotes.get("default_quote_validity", "")).strip(),
                "default_signature_lines": signature_lines,
            },
        }

        save_settings(cleaned_settings)
        return jsonify({"status": "success", "message": "Settings saved successfully."})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


@app.route("/api/quotes", methods=["GET"])
def get_quotes():
    quotes_db = Quote.query.order_by(Quote.date_created.desc(), Quote.quote_number.desc()).all()
    quotes_list = []

    for q in quotes_db:
        q_dict = q.to_dict()
        q_dict["line_item_count"] = len(q.line_items)
        q_dict["edit_url"] = f"/quotes/{q.quote_number}/edit"
        q_dict["pdf_url"] = f"/generate-pdf/{q.quote_number}"
        quotes_list.append(q_dict)

    return jsonify({"status": "success", "quotes": quotes_list})


@app.route("/export/quote-log", methods=["GET"])
def export_quote_log():
    export_rows = get_export_rows()

    export_fieldnames = [
        "Quote Number",
        "Customer",
        "Project Description",
        "Quote Total",
        "Disposition",
        "Date Created",
    ]

    csvfile = io.StringIO(newline="")
    writer = csv.DictWriter(csvfile, fieldnames=export_fieldnames)
    writer.writeheader()
    for row in export_rows:
        values = {key: row.get(key, "") for key in export_fieldnames}
        for key, value in values.items():
            if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
                values[key] = "'" + value
        writer.writerow(values)

    return send_file(
        io.BytesIO(csvfile.getvalue().encode("utf-8")),
        as_attachment=True,
        download_name="quote_log_export.csv",
        mimetype="text/csv",
    )


@app.route("/api/quotes/<quote_number>", methods=["GET"])
def get_quote(quote_number):
    quote = load_quote(quote_number)
    if not quote:
        return jsonify({"status": "error", "message": "Quote not found."}), 404
    return jsonify({"status": "success", "quote": quote})


@app.route("/preview-pdf")
def preview_pdf():
    sample_quote = {
        "quote_number": "PREVIEW-001",
        "branch_id": "325",
        "date_created": datetime.now().strftime("%Y-%m-%d"),
        "customer": "Sample Customer Inc.",
        "customer_contact": "Jane Smith",
        "customer_email": "jane.smith@example.com",
        "project_description": "Template Live Preview Test",
        "disposition": "pending",
        "quote_total": 4500.00,
        "line_items": [
            {
                "item_name": "Premium Pump A",
                "item_description": "Industrial grade high-flow pump",
                "item_long_description": "Detailed specs: 500 GPM, 150 PSI, Stainless Steel construction with double mechanical seal.",
                "quantity": 1,
                "net_cost_each": 2500.00,
                "sell_price_each": 3500.00,
                "gross_margin_percent": 28.57,
                "lead_time": "4 Weeks",
                "line_total": 3500.00,
            },
            {
                "item_name": "Standard Valve B",
                "item_description": "Control valve 2-inch",
                "item_long_description": "Flanged connection, carbon steel body, pneumatic actuator included.",
                "quantity": 2,
                "net_cost_each": 400.00,
                "sell_price_each": 500.00,
                "gross_margin_percent": 20.00,
                "lead_time": "Ex-Stock",
                "line_total": 1000.00,
            },
        ],
        "attachments": [],
    }

    output_path = OUTPUT_DIR / "preview_test.pdf"
    settings = load_settings()

    try:
        if WEB_CONFIG:
            with tempfile.TemporaryDirectory(dir=OUTPUT_DIR) as folder:
                preview_path = Path(folder) / "preview.pdf"
                build_quote_pdf(sample_quote, preview_path, settings, upload_root=UPLOAD_DIR)
                pdf_bytes = preview_path.read_bytes()
            return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf", download_name="preview.pdf")
        build_quote_pdf(
            quote=sample_quote,
            pdf_path=output_path,
            settings=settings,
        )
        response = send_file(str(output_path), mimetype="application/pdf")
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        return f"Error generating preview PDF: {str(e)}", 500


@app.route("/save-quote", methods=["POST"])
def save_quote():
    try:
        data_str = request.form.get("data")
        if data_str:
            data = json.loads(data_str)
        else:
            data = request.get_json(silent=True)

        if not data:
            return jsonify({"status": "error", "message": "No payload received."}), 400

        db.session.execute(text("BEGIN IMMEDIATE"))
        quote_data, error_message = build_quote_payload(data)
        if error_message:
            return jsonify({"status": "error", "message": error_message}), 400

        quote_number = quote_data["quote_number"]

        quote_obj = Quote(
            quote_number=quote_number,
            entry_type=quote_data.get("entry_type", "app"),
            branch_id=quote_data.get("branch_id"),
            date_created=quote_data.get("date_created"),
            customer=quote_data.get("customer"),
            customer_contact=quote_data.get("customer_contact"),
            customer_email=quote_data.get("customer_email"),
            project_description=quote_data.get("project_description"),
            disposition=quote_data.get("disposition"),
            quote_total=quote_data.get("quote_total"),
        )
        db.session.add(quote_obj)
        db.session.flush()

        for li_data in quote_data.get("line_items", []):
            db.session.add(LineItem(
                quote_id=quote_obj.id,
                item_name=li_data.get("item_name"),
                item_description=li_data.get("item_description"),
                item_long_description=li_data.get("item_long_description"),
                quantity=li_data.get("quantity", 1),
                net_cost_each=li_data.get("net_cost_each", 0.0),
                sell_price_each=li_data.get("sell_price_each", 0.0),
                gross_margin_percent=li_data.get("gross_margin_percent", 0.0),
                lead_time=li_data.get("lead_time"),
                line_total=li_data.get("line_total", 0.0),
                item_type=li_data.get("item_type", "single"),
                components=li_data.get("components", []),
            ))

        files = request.files.getlist("attachments")
        if files:
            quote_upload_dir = private_child(UPLOAD_DIR, quote_number)
            quote_upload_dir.mkdir(parents=True, exist_ok=True)
            saved_files = []

            for f in files:
                if f.filename and f.filename.lower().endswith(".pdf"):
                    filename = secure_filename(f.filename)
                    if not filename:
                        raise ValueError("Invalid attachment filename.")
                    filepath = private_child(quote_upload_dir, filename)
                    f.save(str(filepath))
                    saved_files.append(filename)
                    db.session.add(Attachment(quote_id=quote_obj.id, filename=filename))

            quote_data["attachments"] = saved_files
        else:
            quote_data["attachments"] = []

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": f"Database Error: {e}"}), 500

        add_customer_if_new(quote_data["customer"])

        return jsonify({
            "status": "success",
            "message": f"Quote {quote_data['quote_number']} saved successfully.",
            "quote_number": quote_data["quote_number"],
            "quote_total": quote_data["quote_total"],
            "pdf_url": f"/generate-pdf/{quote_data['quote_number']}",
            "edit_url": f"/quotes/{quote_data['quote_number']}/edit",
        })

    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


@app.route("/update-quote/<quote_number>", methods=["PUT"])
def update_quote(quote_number):
    renamed_upload_dir = False
    try:
        data_str = request.form.get("data")
        if data_str:
            data = json.loads(data_str)
        else:
            data = request.get_json(silent=True)

        if not data:
            return jsonify({"status": "error", "message": "No payload received."}), 400

        quote_obj = Quote.query.filter_by(quote_number=quote_number).first()
        if not quote_obj:
            return jsonify({"status": "error", "message": "Quote not found."}), 404

        quote_data, error_message = build_quote_payload(data, existing_quote_number=quote_number)
        if error_message:
            return jsonify({"status": "error", "message": error_message}), 400

        renamed_quote_number = quote_data["quote_number"]
        old_upload_dir = private_child(UPLOAD_DIR, quote_number)
        new_upload_dir = private_child(UPLOAD_DIR, renamed_quote_number)

        if renamed_quote_number != quote_number and old_upload_dir.exists():
            if new_upload_dir.exists():
                return jsonify({"status": "error", "message": f"Attachment folder already exists for {renamed_quote_number}."}), 400
            shutil.move(str(old_upload_dir), str(new_upload_dir))
            renamed_upload_dir = True

        files = request.files.getlist("attachments")
        if files:
            quote_upload_dir = private_child(UPLOAD_DIR, renamed_quote_number)
            quote_upload_dir.mkdir(parents=True, exist_ok=True)
            saved_files = []

            for f in files:
                if f.filename and f.filename.lower().endswith(".pdf"):
                    filename = secure_filename(f.filename)
                    if not filename:
                        raise ValueError("Invalid attachment filename.")
                    filepath = private_child(quote_upload_dir, filename)
                    f.save(str(filepath))
                    if filename not in quote_data["attachments"]:
                        saved_files.append(filename)

            quote_data["attachments"].extend(saved_files)

        quote_obj.quote_number = renamed_quote_number
        quote_obj.entry_type = quote_data.get("entry_type", quote_obj.entry_type or "app")
        quote_obj.branch_id = quote_data.get("branch_id")
        quote_obj.date_created = quote_data.get("date_created")
        quote_obj.customer = quote_data.get("customer")
        quote_obj.customer_contact = quote_data.get("customer_contact")
        quote_obj.customer_email = quote_data.get("customer_email")
        quote_obj.project_description = quote_data.get("project_description")
        quote_obj.disposition = quote_data.get("disposition")
        quote_obj.quote_total = quote_data.get("quote_total")

        LineItem.query.filter_by(quote_id=quote_obj.id).delete()

        for li_data in quote_data.get("line_items", []):
            db.session.add(LineItem(
                quote_id=quote_obj.id,
                item_name=li_data.get("item_name"),
                item_description=li_data.get("item_description"),
                item_long_description=li_data.get("item_long_description"),
                quantity=li_data.get("quantity", 1),
                net_cost_each=li_data.get("net_cost_each", 0.0),
                sell_price_each=li_data.get("sell_price_each", 0.0),
                gross_margin_percent=li_data.get("gross_margin_percent", 0.0),
                lead_time=li_data.get("lead_time"),
                line_total=li_data.get("line_total", 0.0),
                item_type=li_data.get("item_type", "single"),
                components=li_data.get("components", []),
            ))

        existing_attachment_names = {a.filename for a in quote_obj.attachments}
        for filename in quote_data.get("attachments", []):
            if filename not in existing_attachment_names:
                db.session.add(Attachment(quote_id=quote_obj.id, filename=filename))

        db.session.commit()
        add_customer_if_new(quote_data["customer"])

        return jsonify({
            "status": "success",
            "message": f"Quote {quote_data['quote_number']} updated successfully.",
            "quote_number": quote_data["quote_number"],
            "quote_total": quote_data["quote_total"],
            "pdf_url": f"/generate-pdf/{quote_data['quote_number']}",
            "edit_url": f"/quotes/{quote_data['quote_number']}/edit",
        })

    except ValueError as e:
        db.session.rollback()
        if renamed_upload_dir and new_upload_dir.exists() and not old_upload_dir.exists():
            shutil.move(str(new_upload_dir), str(old_upload_dir))
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        if renamed_upload_dir and new_upload_dir.exists() and not old_upload_dir.exists():
            shutil.move(str(new_upload_dir), str(old_upload_dir))
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


@app.patch("/api/quotes/<quote_number>/disposition")
def update_disposition(quote_number):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or set(data) != {"disposition"}:
        return jsonify(status="error", message="Send only the disposition to update."), 400
    disposition = data["disposition"]
    if not isinstance(disposition, str) or disposition not in {"pending", "won", "lost"}:
        return jsonify(status="error", message="Disposition must be Pending, Won, or Lost."), 400
    try:
        quote = Quote.query.filter_by(quote_number=quote_number).first()
        if quote is None:
            return jsonify(status="error", message="Quote not found."), 404
        quote.disposition = disposition
        db.session.commit()
        return jsonify(status="success", quote_number=quote.quote_number, disposition=disposition)
    except Exception:
        db.session.rollback()
        app.logger.exception("Disposition update failed")
        return jsonify(status="error", message="Could not update disposition. Please try again."), 500


@app.post("/api/quotes/<quote_number>/duplicate")
def duplicate_quote(quote_number):
    created_folder = None
    try:
        # Reserve numbering before reading the source so simultaneous duplicates serialize.
        db.session.execute(text("BEGIN IMMEDIATE"))
        source = Quote.query.filter_by(quote_number=quote_number).first()
        if source is None:
            db.session.rollback()
            return jsonify(status="error", message="Quote not found."), 404
        new_number = generate_quote_number(source.branch_id, load_settings())
        duplicate = Quote(
            quote_number=new_number, entry_type="app", branch_id=source.branch_id,
            date_created=datetime.now().strftime("%Y-%m-%d"), disposition="pending",
            customer=source.customer, customer_contact=source.customer_contact,
            customer_email=source.customer_email, project_description=source.project_description,
            quote_total=source.quote_total,
        )
        db.session.add(duplicate)
        db.session.flush()
        for item in source.line_items:
            duplicate.line_items.append(LineItem(**item.to_dict()))
        if source.attachments:
            target = private_child(UPLOAD_DIR, new_number)
            target.mkdir()  # Never merge with or overwrite another quote's attachment folder.
            created_folder = target
            for attachment in source.attachments:
                original = private_child(UPLOAD_DIR, quote_number, attachment.filename)
                if not original.is_file():
                    raise ValueError("A source attachment is missing; restore it before duplicating.")
                shutil.copy2(original, private_child(target, attachment.filename))
                duplicate.attachments.append(Attachment(filename=attachment.filename))
        db.session.commit()
        return jsonify(status="success", quote_number=new_number,
                       edit_url=f"/quotes/{new_number}/edit")
    except (ValueError, FileExistsError) as error:
        db.session.rollback()
        if created_folder:
            shutil.rmtree(created_folder)
        return jsonify(status="error", message=str(error)), 400
    except Exception:
        db.session.rollback()
        if created_folder:
            shutil.rmtree(created_folder)
        app.logger.exception("Quote duplication failed")
        return jsonify(status="error", message="Unable to duplicate quote. No copy was saved."), 500


@app.route("/generate-pdf/<quote_number>")
def generate_pdf(quote_number):
    try:
        quote = load_quote(quote_number)
        if not quote:
            return f"Quote file not found: {escape(quote_number)}", 404

        settings = load_settings()
        if WEB_CONFIG:
            # Each request gets its own output so concurrent views cannot overwrite a PDF.
            with tempfile.TemporaryDirectory(dir=OUTPUT_DIR) as folder:
                pdf_path = Path(folder) / "quote.pdf"
                build_quote_pdf(quote, pdf_path, settings, upload_root=UPLOAD_DIR)
                pdf_bytes = pdf_path.read_bytes()
            return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                             download_name=f"{secure_filename(quote_number)}.pdf")
        pdf_path = private_child(OUTPUT_DIR, f"{quote_number}.pdf")

        build_quote_pdf(
            quote=quote,
            pdf_path=pdf_path,
            settings=settings,
            upload_root=UPLOAD_DIR,
        )

        return send_file(pdf_path, as_attachment=False)

    except Exception as e:
        app.logger.exception("PDF generation failed")
        return f"PDF generation failed: {str(e)}", 500


@app.route("/delete-quote/<quote_number>", methods=["DELETE"])
def delete_quote(quote_number):
    try:
        deleted = delete_quote_data(quote_number)
        if not deleted:
            return jsonify({"status": "error", "message": "Quote not found."}), 404

        return jsonify({
            "status": "success",
            "message": f"Quote {quote_number} deleted successfully.",
            "redirect_url": "/",
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500

def auto_launch_browser():
    import webbrowser
    webbrowser.open("http://127.0.0.1:5000")


def init_db():
    with app.app_context():
        db.create_all()
        item_columns = {row[1] for row in db.session.execute(text("PRAGMA table_info(line_item)"))}
        if "item_type" not in item_columns:
            db.session.execute(text("ALTER TABLE line_item ADD COLUMN item_type VARCHAR(20) NOT NULL DEFAULT 'single'"))
        if "components" not in item_columns:
            db.session.execute(text("ALTER TABLE line_item ADD COLUMN components JSON"))
        db.session.commit()
        columns = {
            row[1]
            for row in db.session.execute(text("PRAGMA table_info(quote)")).fetchall()
        }

        if "entry_type" not in columns:
            db.session.execute(text("ALTER TABLE quote ADD COLUMN entry_type VARCHAR(20) DEFAULT 'app'"))
            db.session.execute(text("UPDATE quote SET entry_type = 'app' WHERE entry_type IS NULL OR entry_type = ''"))
            db.session.commit()

        # Optional migration from legacy JSON quote files
        if Quote.query.count() == 0 and QUOTES_DIR.exists():
            print("Running initial JSON to SQLite migration...")

            for quote_file in QUOTES_DIR.glob("*.json"):
                try:
                    with open(quote_file, "r", encoding="utf-8") as f:
                        q_data = json.load(f)

                    quote_number = q_data.get("quote_number", quote_file.stem)

                    if Quote.query.filter_by(quote_number=quote_number).first():
                        continue

                    q_obj = Quote(
                        quote_number=quote_number,
                        entry_type=normalize_entry_type(q_data.get("entry_type")),
                        branch_id=q_data.get("branch_id"),
                        date_created=q_data.get("date_created"),
                        customer=q_data.get("customer"),
                        customer_contact=q_data.get("customer_contact"),
                        customer_email=q_data.get("customer_email"),
                        project_description=q_data.get("project_description"),
                        disposition=q_data.get("disposition", "pending").lower(),
                        quote_total=q_data.get("quote_total", 0.0),
                    )
                    db.session.add(q_obj)
                    db.session.flush()

                    for li_data in q_data.get("line_items", []):
                        li_obj = LineItem(
                            quote_id=q_obj.id,
                            item_name=li_data.get("item_name"),
                            item_description=li_data.get("item_description"),
                            item_long_description=li_data.get("item_long_description"),
                            quantity=li_data.get("quantity", 1),
                            net_cost_each=li_data.get("net_cost_each", 0.0),
                            sell_price_each=li_data.get("sell_price_each", 0.0),
                            gross_margin_percent=li_data.get("gross_margin_percent", 0.0),
                            lead_time=li_data.get("lead_time"),
                            line_total=li_data.get("line_total", 0.0),
                            item_type=li_data.get("item_type", "single"),
                            components=li_data.get("components", []),
                        )
                        db.session.add(li_obj)

                    for att in q_data.get("attachments", []):
                        att_obj = Attachment(quote_id=q_obj.id, filename=att)
                        db.session.add(att_obj)

                except Exception as e:
                    print(f"Failed to migrate {quote_file}: {e}")

            db.session.commit()
            print("Migration complete!")


if __name__ == "__main__":
    if WEB_CONFIG:
        raise SystemExit("Use manage_web.py init and a WSGI deployment; desktop startup is disabled in web mode.")
    ensure_settings_file()
    init_db()

    import threading
    threading.Timer(1.5, auto_launch_browser).start()

    app.run(host="127.0.0.1", debug=False, use_reloader=False)
