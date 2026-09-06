import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from storage_paths import private_child
from web_security import load_web_config

URL = "https://quotes.example.test"


def import_app(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "app.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class WebModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.config_path = cls.base / "web-config.json"
        cls.config = {
            "host": "quotes.example.test", "username": "abel",
            "password_hash": generate_password_hash("test-password-only", method="pbkdf2:sha256:1000"),
            "secret_key": "test-only-secret-" * 4,
            "storage_root": str(cls.base / "private"),
            "public_root": str(cls.base / "public"),
        }
        cls.config_path.write_text(json.dumps(cls.config), encoding="utf-8")
        cls.env = patch.dict(os.environ, {"QUOTE_TOOL_WEB": "1", "QUOTE_TOOL_CONFIG": str(cls.config_path)})
        cls.env.start()
        cls.module = import_app("web_test_app")
        cls.app = cls.module.app
        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            cls.module.db.session.remove()
            cls.module.db.engine.dispose()
        cls.env.stop()
        cls.temp.cleanup()

    def setUp(self):
        with self.app.app_context():
            self.module.db.drop_all()
        self.module.init_db()
        throttle = self.base / "private" / "login-attempts.sqlite3"
        if throttle.exists():
            throttle.unlink()
        self.module.save_settings(self.module.DEFAULT_SETTINGS)
        self.client = self.app.test_client()

    def request(self, path, method="GET", **kwargs):
        return self.client.open(path, method=method, base_url=URL, **kwargs)

    def token(self, client=None):
        response = (client or self.client).get("/login", base_url=URL)
        return re.search(rb'name="csrf_token" value="([^"]+)"', response.data)[1].decode()

    def login(self):
        response = self.request("/login", "POST", data={
            "username": "abel", "password": "test-password-only", "csrf_token": self.token()})
        self.assertEqual(response.status_code, 302)
        return self.token()

    def payload(self, **overrides):
        data = {
            "branch_id": "325", "customer": "Synthetic Customer",
            "project_description": "Staging test", "disposition": "pending",
            "line_items": [{"item_name": "Pump", "quantity": 2,
                            "net_cost_each": 50, "sell_price_each": 100}],
        }
        data.update(overrides)
        return data

    def save(self, token, payload=None):
        response = self.request("/save-quote", "POST", json=payload or self.payload(),
                                headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200, response.data)
        return response.json["quote_number"]

    def test_anonymous_data_routes_are_protected(self):
        for path in ("/", "/api/quotes", "/api/settings", "/quote-tool", "/p21-quote",
                     "/settings", "/preview-pdf", "/generate-pdf/test", "/export/quote-log",
                     "/api/quotes/test", "/quotes/test/edit"):
            with self.subTest(path=path):
                self.assertEqual(self.request(path).status_code, 401)
        self.assertEqual(self.request("/", headers={"Accept": "text/html"}).location, "/login")
        self.assertEqual(self.request("/save-quote", "POST", json=self.payload()).status_code, 401)

    def test_https_and_host_are_enforced(self):
        self.assertEqual(self.client.get("/login", base_url="http://quotes.example.test").status_code, 400)
        self.assertEqual(self.client.get("/login", base_url="https://evil.example").status_code, 400)
        self.assertEqual(self.client.get("/login", base_url="http://quotes.example.test",
                         headers={"X-Forwarded-Proto": "https"}).status_code, 400)

    def test_login_csrf_and_session_rotation(self):
        old_token = self.token()
        self.assertEqual(self.request("/login", "POST", data={"username": "abel",
                         "password": "test-password-only"}).status_code, 400)
        token = self.login()
        self.assertNotEqual(token, old_token)
        self.assertEqual(self.request("/api/quotes").status_code, 200)
        self.assertEqual(self.request("/save-quote", "POST", json=self.payload()).status_code, 400)
        self.assertEqual(self.request("/save-quote", "POST", json=self.payload(),
                         headers={"X-CSRF-Token": old_token}).status_code, 400)

    def test_login_throttle_is_shared_by_clients(self):
        token = self.token()
        for _ in range(10):
            response = self.request("/login", "POST", data={"username": "abel", "password": "wrong",
                                                               "csrf_token": token})
            self.assertEqual(response.status_code, 401)
        another = self.app.test_client()
        response = another.post("/login", base_url=URL, data={"username": "abel",
            "password": "test-password-only", "csrf_token": self.token(another)})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "900")

    def test_logout_requires_csrf_and_removes_access(self):
        token = self.login()
        self.assertEqual(self.request("/logout", "GET").status_code, 405)
        self.assertEqual(self.request("/logout", "POST").status_code, 400)
        self.assertEqual(self.request("/logout", "POST", data={"csrf_token": token}).status_code, 302)
        self.assertEqual(self.request("/api/quotes").status_code, 401)

    def test_cookie_and_csp_headers(self):
        response = self.request("/login")
        cookie = response.headers["Set-Cookie"]
        for flag in ("__Host-quote_session=", "Secure", "HttpOnly", "SameSite=Lax", "Path=/"):
            self.assertIn(flag, cookie)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.login()
        response = self.request("/")
        nonce = re.search(rb'<script nonce="([^"]+)"', response.data)[1].decode()
        self.assertIn(f"'nonce-{nonce}'", response.headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", response.headers["Content-Security-Policy"].split("script-src")[1].split(";")[0])

    def test_save_edit_p21_and_delete(self):
        token = self.login()
        number = self.save(token)
        response = self.request(f"/update-quote/{number}", "PUT", headers={"X-CSRF-Token": token},
                                json=self.payload(quote_number="P21-EXTERNAL-12", date_created="2025-04-10", entry_type="p21"))
        self.assertEqual(response.status_code, 200, response.data)
        saved = self.request("/api/quotes/P21-EXTERNAL-12").json["quote"]
        self.assertEqual(saved["date_created"], "2025-04-10")
        self.assertEqual(saved["quote_total"], 200)
        self.assertEqual(self.request("/delete-quote/P21-EXTERNAL-12", "DELETE").status_code, 400)
        self.assertEqual(self.request("/delete-quote/P21-EXTERNAL-12", "DELETE",
                         headers={"X-CSRF-Token": token}).status_code, 200)
        self.assertEqual(self.request("/api/quotes").json["quotes"], [])

    def package(self):
        return {
            "item_type": "package", "item_name": "Customer pump package", "quantity": 3,
            "net_cost_each": 999999, "sell_price_each": 1,
            "components": [
                {"item_name": "PRIVATE motor SKU", "quantity": 2, "net_cost_each": 30.15, "sell_price_each": 50.25},
                {"item_name": "PRIVATE seal SKU", "quantity": 1, "net_cost_each": 4.70, "sell_price_each": 9.50},
            ],
        }

    def test_package_round_trip_and_pdf_privacy(self):
        token = self.login()
        number = self.save(token, self.payload(line_items=[self.package()]))
        quote = self.request(f"/api/quotes/{number}").json["quote"]
        item = quote["line_items"][0]
        self.assertEqual(item["net_cost_each"], 65)
        self.assertEqual(item["sell_price_each"], 110)
        self.assertEqual(quote["quote_total"], 330)
        self.assertEqual(len(item["components"]), 2)
        pdf = self.request(f"/generate-pdf/{number}")
        self.assertEqual(pdf.status_code, 200)
        text = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf.data)).pages)
        self.assertIn("Customer pump package", " ".join(text.split()))
        self.assertNotIn("PRIVATE", text)
        self.assertNotIn("30.15", text)
        quote["line_items"][0]["components"][0]["sell_price_each"] = 60.25
        response = self.request(f"/update-quote/{number}", "PUT", json=quote, headers={"X-CSRF-Token": token})
        self.assertEqual(response.status_code, 200)
        updated = self.request(f"/api/quotes/{number}").json["quote"]
        self.assertEqual(updated["quote_total"], 390)
        self.assertEqual(updated["line_items"][0]["item_type"], "package")

    def test_package_validation_and_currency_rounding(self):
        token = self.login()
        invalid = []
        for change in ({"components": []}, {"components": "bad"}, {"quantity": 1.5}, {"quantity": 0}):
            item = self.package()
            item.update(change)
            invalid.append(item)
        for change in ({"quantity": -1}, {"quantity": "NaN"}, {"net_cost_each": -1},
                       {"sell_price_each": "Infinity"}, {"item_name": ""}, {"item_type": "package"}):
            item = self.package()
            item["components"][0].update(change)
            invalid.append(item)
        for item in invalid:
            with self.subTest(item=item):
                response = self.request("/save-quote", "POST", json=self.payload(line_items=[item]), headers={"X-CSRF-Token": token})
                self.assertEqual(response.status_code, 400, response.data)
        item = self.package()
        item["components"][0].update(sell_price_each=0, net_cost_each=0)
        self.assertEqual(self.module.calculate_line_item(item)["line_total"], 28.5)
        single = self.module.calculate_line_item({"item_name": "Round", "quantity": 3, "net_cost_each": 0, "sell_price_each": "1.005"})
        self.assertEqual(single["sell_price_each"], 1.01)
        self.assertEqual(single["line_total"], 3.03)

    def test_duplicate_copies_package_and_resets_metadata(self):
        from datetime import datetime
        token = self.login()
        source = self.save(token, self.payload(entry_type="p21", quote_number="P21-OLD", date_created="2024-01-02",
                                            disposition="won", line_items=[self.package()]))
        original = self.request(f"/api/quotes/{source}").json["quote"]
        copies = []
        for _ in range(2):
            result = self.request(f"/api/quotes/{source}/duplicate", "POST", headers={"X-CSRF-Token": token})
            self.assertEqual(result.status_code, 200, result.data)
            copies.append(result.json["quote_number"])
        self.assertNotEqual(copies[0], copies[1])
        duplicate = self.request(f"/api/quotes/{copies[0]}").json["quote"]
        self.assertEqual(duplicate["date_created"], datetime.now().strftime("%Y-%m-%d"))
        self.assertEqual(duplicate["entry_type"], "app")
        self.assertEqual(duplicate["disposition"], "pending")
        self.assertEqual(duplicate["line_items"], original["line_items"])
        duplicate["line_items"][0]["components"][0]["sell_price_each"] = 500
        self.assertEqual(self.request(f"/update-quote/{copies[0]}", "PUT", json=duplicate, headers={"X-CSRF-Token": token}).status_code, 200)
        self.assertEqual(self.request(f"/api/quotes/{source}").json["quote"], original)
        self.assertEqual(self.request(f"/delete-quote/{copies[0]}", "DELETE", headers={"X-CSRF-Token": token}).status_code, 200)
        self.assertEqual(self.request(f"/api/quotes/{source}").json["quote"], original)

    def test_duplicate_attachments_are_independent_and_missing_files_abort(self):
        token = self.login()
        number = self.save(token)
        folder = self.module.UPLOAD_DIR / number
        folder.mkdir()
        original = folder / "annex.pdf"
        original.write_bytes(b"synthetic attachment bytes")
        with self.app.app_context():
            quote = self.module.Quote.query.filter_by(quote_number=number).first()
            quote.attachments.append(self.module.Attachment(filename="annex.pdf"))
            self.module.db.session.commit()
        result = self.request(f"/api/quotes/{number}/duplicate", "POST", headers={"X-CSRF-Token": token})
        self.assertEqual(result.status_code, 200, result.data)
        copied = self.module.UPLOAD_DIR / result.json["quote_number"] / "annex.pdf"
        self.assertEqual(copied.read_bytes(), original.read_bytes())
        copied.write_bytes(b"changed copy")
        self.assertNotEqual(copied.read_bytes(), original.read_bytes())
        original.unlink()
        before = set(self.module.UPLOAD_DIR.iterdir())
        result = self.request(f"/api/quotes/{number}/duplicate", "POST", headers={"X-CSRF-Token": token})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(set(self.module.UPLOAD_DIR.iterdir()), before)
        self.assertEqual(len(self.request("/api/quotes").json["quotes"]), 2)

    def test_duplicate_auth_csrf_missing_and_safe_methods(self):
        self.assertEqual(self.request("/api/quotes/test/duplicate", "POST").status_code, 401)
        token = self.login()
        self.assertEqual(self.request("/api/quotes/test/duplicate", "POST").status_code, 400)
        self.assertEqual(self.request("/api/quotes/test/duplicate", "GET").status_code, 405)
        self.assertEqual(self.request("/api/quotes/test/duplicate", "POST", headers={"X-CSRF-Token": token}).status_code, 404)

    def test_existing_schema_migration_is_additive_and_repeatable(self):
        import sqlite3
        from contextlib import closing
        token = self.login()
        number = self.save(token)
        original = self.request(f"/api/quotes/{number}").json["quote"]
        with self.app.app_context():
            self.module.db.session.remove()
            self.module.db.engine.dispose()
        with closing(sqlite3.connect(self.module.DB_FILE)) as connection, connection:
            connection.execute("ALTER TABLE line_item DROP COLUMN components")
            connection.execute("ALTER TABLE line_item DROP COLUMN item_type")
        self.module.init_db()
        self.module.init_db()
        self.assertEqual(self.request(f"/api/quotes/{number}").json["quote"], original)

    def test_settings_require_csrf(self):
        token = self.login()
        data = self.module.DEFAULT_SETTINGS
        self.assertEqual(self.request("/api/settings", "POST", json=data).status_code, 400)
        self.assertEqual(self.request("/api/settings", "POST", json=data,
                         headers={"X-CSRF-Token": token}).status_code, 200)
        for path in ("/settings", "/quote-tool", "/p21-quote"):
            response = self.request(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'csrf-token', response.data)

    def test_private_pdf_attachments_and_export(self):
        token = self.login()
        attachment = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(attachment)
        attachment.seek(0)
        response = self.request("/save-quote", "POST", headers={"X-CSRF-Token": token}, data={
            "data": json.dumps(self.payload(customer="=1+1")), "attachments": (attachment, "annex.pdf")})
        self.assertEqual(response.status_code, 200, response.data)
        number = response.json["quote_number"]
        pdf = self.request(f"/generate-pdf/{number}")
        self.assertEqual(pdf.status_code, 200, pdf.data[:500])
        pages = PdfReader(io.BytesIO(pdf.data)).pages
        self.assertGreaterEqual(len(pages), 3)
        self.assertEqual(float(pages[1].mediabox.width), 72)
        self.assertTrue((self.module.UPLOAD_DIR / number / "annex.pdf").exists())
        self.assertFalse(list(self.module.OUTPUT_DIR.iterdir()))
        self.assertIn(b"'=1+1", self.request("/export/quote-log").data)

    def test_bad_quote_numbers_and_nonfinite_prices(self):
        token = self.login()
        for number in ("../escape", "/tmp/escape", ".", "..", "P21/12"):
            response = self.request("/save-quote", "POST", headers={"X-CSRF-Token": token},
                json=self.payload(entry_type="p21", quote_number=number, date_created="2025-01-01"))
            self.assertEqual(response.status_code, 400)
        with self.assertRaises(ValueError):
            self.module.calculate_line_item({"sell_price_each": "Infinity"})
        with self.assertRaises(ValueError):
            private_child(self.module.UPLOAD_DIR, "../../outside")

    def test_server_error_details_are_hidden(self):
        self.login()
        with patch.object(self.module, "load_quote", side_effect=RuntimeError("PRIVATE-PATH-SECRET")):
            response = self.request("/generate-pdf/test")
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b"PRIVATE-PATH-SECRET", response.data)

    def test_configuration_fails_closed(self):
        with patch.dict(os.environ, {"QUOTE_TOOL_CONFIG": str(self.base / "missing.json")}):
            with self.assertRaises(RuntimeError):
                load_web_config()

    def test_csrf_tokens_cannot_be_shared_between_sessions(self):
        first_token = self.login()
        other = self.app.test_client()
        other_token = self.token(other)
        response = other.post("/login", base_url=URL, data={"username": "abel",
            "password": "test-password-only", "csrf_token": other_token})
        self.assertEqual(response.status_code, 302)
        response = other.post("/save-quote", base_url=URL, json=self.payload(),
                              headers={"X-CSRF-Token": first_token})
        self.assertEqual(response.status_code, 400)

    def test_upload_request_size_is_limited(self):
        self.login()
        with patch.dict(self.app.config, {"MAX_CONTENT_LENGTH": 128}):
            response = self.request("/save-quote", "POST", data={"data": "x" * 256})
        self.assertEqual(response.status_code, 413)

    def test_private_files_are_not_static_assets(self):
        self.login()
        for path in ("/data/quotes.db", "/static/../data/quotes.db", "/web-config.json"):
            self.assertEqual(self.request(path).status_code, 404)

    def test_pdf_template_escapes_customer_markup(self):
        token = self.login()
        number = self.save(token, self.payload(customer='<img src="https://example.invalid/probe">'))
        captured = []
        from pdf_generator import convert_html_to_pdf
        def capture(html):
            captured.append(html)
            return convert_html_to_pdf(html)
        with patch("pdf_generator.convert_html_to_pdf", side_effect=capture):
            response = self.request(f"/generate-pdf/{number}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("&lt;img", captured[0])
        self.assertNotIn('<img src="https://example.invalid/probe">', captured[0])

    def test_quote_number_rename_moves_private_attachments(self):
        token = self.login()
        number = self.save(token)
        folder = self.module.UPLOAD_DIR / number
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "placeholder.pdf").write_bytes(b"synthetic")
        response = self.request(f"/update-quote/{number}", "PUT", headers={"X-CSRF-Token": token},
                                json=self.payload(quote_number="RENAMED-12"))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(folder.exists())
        self.assertTrue((self.module.UPLOAD_DIR / "RENAMED-12" / "placeholder.pdf").exists())

    def test_setup_prompts_for_password_and_never_overwrites_config(self):
        import manage_web
        path = self.base / "generated-config.json"
        args = ["manage_web.py", "configure", "--config", str(path),
                "--storage-root", str(self.base / "new-private"),
                "--public-root", str(self.base / "new-public"),
                "--host", "quotes.example.test", "--username", "abel"]
        with patch.object(sys, "argv", args), patch("getpass.getpass", return_value="long-test-password-only"):
            manage_web.main()
            text = path.read_text()
            self.assertNotIn("long-test-password-only", text)
            self.assertFalse(json.loads(text)["allow_reference_cgi"])
            with self.assertRaises(SystemExit):
                manage_web.main()
            self.assertEqual(path.read_text(), text)
        bad = dict(self.config, storage_root=str(self.base / "public" / "data"))
        path = self.base / "bad-config.json"
        path.write_text(json.dumps(bad))
        with patch.dict(os.environ, {"QUOTE_TOOL_CONFIG": str(path)}):
            with self.assertRaises(RuntimeError):
                load_web_config()

    def test_web_init_and_wsgi_entry(self):
        result = subprocess.run([sys.executable, "manage_web.py", "init", "--config", str(self.config_path)],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, "-c", "from wsgi import application; assert application.config['WEB_MODE']"],
                                cwd=ROOT, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)


class DesktopTests(unittest.TestCase):
    def test_desktop_remains_login_free_and_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {"QUOTE_TOOL_WEB": "0", "QUOTE_TOOL_STORAGE_ROOT": folder}):
                module = import_app("desktop_test_app")
                module.init_db()
                client = module.app.test_client()
                self.assertFalse(module.app.config["WEB_MODE"])
                self.assertEqual(client.get("/").status_code, 200)
                self.assertEqual(client.get("/api/quotes").status_code, 200)
                self.assertEqual(client.get("/login").status_code, 404)
                self.assertEqual(module.DATA_DIR, Path(folder) / "data")
                with module.app.app_context():
                    module.db.session.remove()
                    module.db.engine.dispose()


if __name__ == "__main__":
    unittest.main()
