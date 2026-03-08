from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
from datetime import datetime
import json
import csv

from pdf_generator import build_quote_pdf

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
QUOTES_DIR = DATA_DIR / "quotes"
CUSTOMERS_FILE = DATA_DIR / "customers.json"
QUOTE_LOG_FILE = DATA_DIR / "quote_log.csv"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_FILE = ASSETS_DIR / "dxp_logo.png"

SALES_ENGINEER_NAME = "Abel Reji"
SALES_ENGINEER_PHONE = "(918) 703-7381"
SALES_ENGINEER_EMAIL = "Abel.Reji@dxpe.com"

DATA_DIR.mkdir(parents=True, exist_ok=True)
QUOTES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)


@app.route("/")
def landing_page():
    return render_template("landing.html")


@app.route("/quote-tool")
def quote_tool():
    return render_template("index.html", edit_mode=False, quote=None)


@app.route("/quotes/<quote_number>/edit")
def edit_quote_page(quote_number):
    quote = load_quote(quote_number)
    if not quote:
        return f"Quote file not found: {quote_number}", 404

    return render_template("index.html", edit_mode=True, quote=quote)


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


def generate_quote_number(branch_id: str) -> str:
    today = datetime.now()
    date_code = today.strftime("%y%m%d")

    existing_count = 0
    for _ in QUOTES_DIR.glob(f"{branch_id}-{date_code}*AR.json"):
        existing_count += 1

    daily_sequence = existing_count + 1
    return f"{branch_id}-{date_code}{daily_sequence}AR"


def calculate_line_item(item: dict) -> dict:
    quantity = safe_int(item.get("quantity"), 1)
    net_cost_each = safe_float(item.get("net_cost_each"), 0.0)
    sell_price_each = safe_float(item.get("sell_price_each"), 0.0)
    gross_margin_percent = safe_float(item.get("gross_margin_percent"), 0.0)

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if net_cost_each < 0:
        raise ValueError("Net cost cannot be negative.")

    if sell_price_each <= 0 and gross_margin_percent > 0:
        margin_decimal = gross_margin_percent / 100.0
        if margin_decimal >= 1:
            raise ValueError("Gross margin percent must be less than 100.")
        sell_price_each = net_cost_each / (1 - margin_decimal)

    elif gross_margin_percent <= 0 and sell_price_each > 0:
        gross_margin_percent = ((sell_price_each - net_cost_each) / sell_price_each) * 100.0

    if sell_price_each <= 0:
        raise ValueError("Sell price must be greater than zero.")

    line_total = quantity * sell_price_each

    return {
        "item_name": str(item.get("item_name", "")).strip(),
        "item_description": str(item.get("item_description", "")).strip(),
        "item_long_description": str(item.get("item_long_description", "")).strip(),
        "quantity": quantity,
        "net_cost_each": round(net_cost_each, 2),
        "sell_price_each": round(sell_price_each, 2),
        "gross_margin_percent": round(gross_margin_percent, 2),
        "lead_time": str(item.get("lead_time", "")).strip(),
        "line_total": round(line_total, 2),
    }


def ensure_quote_log_exists():
    if not QUOTE_LOG_FILE.exists():
        with open(QUOTE_LOG_FILE, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                "QuoteNumber",
                "DateCreated",
                "Customer",
                "ProjectDescription",
                "QuoteTotal",
                "Disposition"
            ])


def append_quote_log(quote_data: dict):
    ensure_quote_log_exists()
    with open(QUOTE_LOG_FILE, "a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            quote_data["quote_number"],
            quote_data["date_created"],
            quote_data["customer"],
            quote_data["project_description"],
            quote_data["quote_total"],
            quote_data["disposition"],
        ])


def update_quote_log(quote_data: dict):
    ensure_quote_log_exists()

    rows = []
    found = False
    with open(QUOTE_LOG_FILE, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames or [
            "QuoteNumber",
            "DateCreated",
            "Customer",
            "ProjectDescription",
            "QuoteTotal",
            "Disposition",
        ]

        for row in reader:
            if row.get("QuoteNumber") == quote_data["quote_number"]:
                row = {
                    "QuoteNumber": quote_data["quote_number"],
                    "DateCreated": quote_data["date_created"],
                    "Customer": quote_data["customer"],
                    "ProjectDescription": quote_data["project_description"],
                    "QuoteTotal": quote_data["quote_total"],
                    "Disposition": quote_data.get("disposition", ""),
                }
                found = True
            rows.append(row)

    if not found:
        rows.append({
            "QuoteNumber": quote_data["quote_number"],
            "DateCreated": quote_data["date_created"],
            "Customer": quote_data["customer"],
            "ProjectDescription": quote_data["project_description"],
            "QuoteTotal": quote_data["quote_total"],
            "Disposition": quote_data.get("disposition", ""),
        })

    with open(QUOTE_LOG_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

def delete_quote_log_entry(quote_number: str):
    ensure_quote_log_exists()

    rows = []
    with open(QUOTE_LOG_FILE, "r", newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = reader.fieldnames or [
            "QuoteNumber",
            "DateCreated",
            "Customer",
            "ProjectDescription",
            "QuoteTotal",
            "Disposition",
        ]

        for row in reader:
            if row.get("QuoteNumber") != quote_number:
                rows.append(row)

    with open(QUOTE_LOG_FILE, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

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
    with open(CUSTOMERS_FILE, "w", encoding="utf-8") as f:
        json.dump(customers, f, indent=2)


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


def quote_file_path(quote_number: str) -> Path:
    return QUOTES_DIR / f"{quote_number}.json"


def load_quote(quote_number: str):
    file_path = quote_file_path(quote_number)
    if not file_path.exists():
        return None

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_quote_payload(data: dict, existing_quote_number: str | None = None) -> dict:
    branch_id = str(data.get("branch_id", "")).strip()
    customer = str(data.get("customer", "")).strip()
    project_description = str(data.get("project_description", "")).strip()
    line_items_in = data.get("line_items", [])
    disposition = str(data.get("disposition", "pending")).strip().lower() or "pending"

    if branch_id not in {"325", "190"}:
        raise ValueError("Invalid branch ID.")

    if not customer:
        raise ValueError("Customer is required.")

    if not project_description:
        raise ValueError("Project description is required.")

    if not line_items_in:
        raise ValueError("At least one line item is required.")

    if disposition not in {"won", "lost", "pending"}:
        raise ValueError("Invalid disposition.")

    processed_line_items = [calculate_line_item(item) for item in line_items_in]
    quote_total = round(sum(item["line_total"] for item in processed_line_items), 2)

    if existing_quote_number:
        existing_quote = load_quote(existing_quote_number)
        if not existing_quote:
            raise ValueError(f"Quote file not found: {existing_quote_number}")
        quote_number = existing_quote_number
        date_created = existing_quote.get("date_created") or datetime.now().strftime("%Y-%m-%d")
    else:
        quote_number = generate_quote_number(branch_id)
        date_created = datetime.now().strftime("%Y-%m-%d")

    return {
        "quote_number": quote_number,
        "branch_id": branch_id,
        "date_created": date_created,
        "customer": customer,
        "project_description": project_description,
        "disposition": disposition,
        "line_items": processed_line_items,
        "quote_total": quote_total,
    }


def save_quote_json(quote_data: dict):
    quote_file = quote_file_path(quote_data["quote_number"])
    with open(quote_file, "w", encoding="utf-8") as f:
        json.dump(quote_data, f, indent=2)

def get_export_rows() -> list[dict]:
    rows = []

    for quote_file in sorted(QUOTES_DIR.glob("*.json"), reverse=True):
        try:
            with open(quote_file, "r", encoding="utf-8") as f:
                quote = json.load(f)

            rows.append({
                "Quote Number": quote.get("quote_number", quote_file.stem),
                "Customer": quote.get("customer", ""),
                "Project Description": quote.get("project_description", ""),
                "Quote Total": quote.get("quote_total", 0),
                "Disposition": quote.get("disposition", "") or "",
                "Date Created": quote.get("date_created", ""),
            })
        except (OSError, json.JSONDecodeError):
            continue

    rows.sort(key=lambda row: (row.get("Date Created", ""), row.get("Quote Number", "")), reverse=True)
    return rows



@app.route("/api/quotes", methods=["GET"])
def get_quotes():
    quotes = []
    for quote_file in sorted(QUOTES_DIR.glob("*.json"), reverse=True):
        try:
            with open(quote_file, "r", encoding="utf-8") as f:
                quote = json.load(f)

            quotes.append({
                "quote_number": quote.get("quote_number", quote_file.stem),
                "date_created": quote.get("date_created", ""),
                "customer": quote.get("customer", ""),
                "project_description": quote.get("project_description", ""),
                "quote_total": quote.get("quote_total", 0),
                "disposition": (quote.get("disposition") or "pending").lower(),
                "line_item_count": len(quote.get("line_items", [])),
                "edit_url": f"/quotes/{quote.get('quote_number', quote_file.stem)}/edit",
                "pdf_url": f"/generate-pdf/{quote.get('quote_number', quote_file.stem)}",
            })
        except (OSError, json.JSONDecodeError):
            continue

    quotes.sort(key=lambda q: (q.get("date_created", ""), q.get("quote_number", "")), reverse=True)
    return jsonify({"status": "success", "quotes": quotes})


@app.route("/export/quote-log", methods=["GET"])
def export_quote_log():
    export_rows = get_export_rows()

    export_fieldnames = [
        "Quote Number",
        "Customer",
        "Project Description",
        "Quote Total",
        "Disposition",
    ]

    ensure_quote_log_exists()

    export_path = OUTPUT_DIR / "quote_log_export.csv"
    with open(export_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=export_fieldnames)
        writer.writeheader()
        for row in export_rows:
            writer.writerow({key: row.get(key, "") for key in export_fieldnames})

    return send_file(export_path, as_attachment=True, download_name="quote_log_export.csv", mimetype="text/csv")


@app.route("/api/quotes/<quote_number>", methods=["GET"])
def get_quote(quote_number):
    quote = load_quote(quote_number)
    if not quote:
        return jsonify({"status": "error", "message": "Quote not found."}), 404
    return jsonify({"status": "success", "quote": quote})


@app.route("/save-quote", methods=["POST"])
def save_quote():
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received."}), 400

        quote_data = build_quote_payload(data)
        save_quote_json(quote_data)
        append_quote_log(quote_data)
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
        print(f"ValueError in save_quote: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"Unexpected error in save_quote: {e}")
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


@app.route("/update-quote/<quote_number>", methods=["PUT"])
def update_quote(quote_number):
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"status": "error", "message": "No JSON payload received."}), 400

        if not load_quote(quote_number):
            return jsonify({"status": "error", "message": "Quote not found."}), 404

        quote_data = build_quote_payload(data, existing_quote_number=quote_number)
        save_quote_json(quote_data)
        update_quote_log(quote_data)
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
        print(f"ValueError in update_quote: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        print(f"Unexpected error in update_quote: {e}")
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


@app.route("/generate-pdf/<quote_number>")
def generate_pdf(quote_number):
    try:
        quote = load_quote(quote_number)

        if not quote:
            return f"Quote file not found: {quote_number}", 404

        pdf_path = OUTPUT_DIR / f"{quote_number}.pdf"

        build_quote_pdf(
            quote=quote,
            pdf_path=pdf_path,
            logo_path=LOGO_FILE,
            sales_engineer_name=SALES_ENGINEER_NAME,
            sales_engineer_phone=SALES_ENGINEER_PHONE,
            sales_engineer_email=SALES_ENGINEER_EMAIL,
        )

        return send_file(pdf_path, as_attachment=False)

    except Exception as e:
        import traceback
        print("Error in generate_pdf:")
        traceback.print_exc()
        return f"PDF generation failed: {str(e)}", 500


@app.route("/delete-quote/<quote_number>", methods=["DELETE"])
def delete_quote(quote_number):
    try:
        quote_file = quote_file_path(quote_number)

        if not quote_file.exists():
            return jsonify({"status": "error", "message": "Quote not found."}), 404

        quote_file.unlink()
        delete_quote_log_entry(quote_number)

        pdf_path = OUTPUT_DIR / f"{quote_number}.pdf"
        if pdf_path.exists():
            pdf_path.unlink()

        return jsonify({
            "status": "success",
            "message": f"Quote {quote_number} deleted successfully.",
        })

    except Exception as e:
        print(f"Unexpected error in delete_quote: {e}")
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
