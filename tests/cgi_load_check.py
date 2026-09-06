"""Bounded, isolated CGI-process smoke/load checks; never uses live credentials/data."""
from concurrent.futures import ThreadPoolExecutor
from email.parser import BytesParser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from pypdf import PdfReader
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
GATEWAY = "from wsgi import application; from wsgiref.handlers import CGIHandler; CGIHandler().run(application)"


def main():
    with tempfile.TemporaryDirectory(prefix="quote-cgi-audit-") as folder:
        base = Path(folder)
        config = base / "config.json"
        config.write_text(json.dumps({
            "host": "quotes.example.test", "username": "audit",
            "password_hash": generate_password_hash("synthetic-test-password", method="pbkdf2:sha256:1000"),
            "secret_key": "synthetic-audit-secret-" * 4,
            "storage_root": str(base / "storage"), "public_root": str(base / "public"),
        }))
        env = dict(os.environ, QUOTE_TOOL_WEB="1", QUOTE_TOOL_CONFIG=str(config))
        subprocess.run([sys.executable, "manage_web.py", "init", "--config", str(config)],
                       cwd=ROOT, env=env, check=True, capture_output=True, timeout=30)

        def request(path, method="GET", payload=None, cookie="", token=""):
            body = json.dumps(payload).encode() if payload is not None else b""
            request_env = dict(env, REQUEST_METHOD=method, PATH_INFO=path, SCRIPT_NAME="",
                               SERVER_NAME="quotes.example.test", HTTP_HOST="quotes.example.test",
                               SERVER_PORT="443", SERVER_PROTOCOL="HTTP/1.1", HTTPS="on",
                               GATEWAY_INTERFACE="CGI/1.1", CONTENT_TYPE="application/json",
                               CONTENT_LENGTH=str(len(body)), HTTP_COOKIE=cookie,
                               HTTP_X_CSRF_TOKEN=token, QUERY_STRING="")
            start = time.monotonic()
            result = subprocess.run([sys.executable, "-c", GATEWAY], cwd=ROOT, env=request_env,
                                    input=body, capture_output=True, timeout=45)
            header, sep, data = result.stdout.partition(b"\r\n\r\n")
            if not sep:
                raise RuntimeError("CGI returned invalid headers: " + result.stderr.decode(errors="replace")[:300])
            headers = BytesParser().parsebytes(header + b"\r\n\r\n")
            status = int(headers.get("Status", "200 OK").split()[0])
            return status, headers, data, round(time.monotonic() - start, 3)

        # A signed fixture session exercises the production auth checks without using the user's credentials.
        from flask import Flask
        from flask.sessions import SecureCookieSessionInterface
        import hashlib
        import hmac
        credentials = json.loads(config.read_text())
        signer_app = Flask("audit-session")
        signer_app.secret_key = credentials["secret_key"]
        tag = hmac.new(credentials["secret_key"].encode(),
                       (credentials["username"] + "\0" + credentials["password_hash"]).encode(), hashlib.sha256).hexdigest()
        token = "synthetic-audit-csrf"
        signed = SecureCookieSessionInterface().get_signing_serializer(signer_app).dumps({"account": tag, "csrf": token})
        cookie = "__Host-quote_session=" + signed
        payload = {"branch_id": "325", "customer": "Synthetic concurrency fixture",
                   "project_description": "CGI process check", "disposition": "pending",
                   "line_items": [{"item_name": "Synthetic pump", "quantity": 1,
                                   "net_cost_each": 50, "sell_price_each": 100}]}
        with ThreadPoolExecutor(max_workers=3) as pool:
            saves = list(pool.map(lambda _: request("/save-quote", "POST", payload, cookie, token), range(6)))
        statuses = [result[0] for result in saves]
        numbers = [json.loads(r[2])["quote_number"] for r in saves if r[0] == 200]
        report = {"save_statuses": statuses, "unique_numbers": len(set(numbers)),
                  "save_seconds": [r[3] for r in saves]}
        if numbers:
            with ThreadPoolExecutor(max_workers=3) as pool:
                duplicates = list(pool.map(lambda _: request(f"/api/quotes/{numbers[0]}/duplicate", "POST", None, cookie, token), range(3)))
            report["duplicate_statuses"] = [r[0] for r in duplicates]
            duplicate_numbers = [json.loads(r[2])["quote_number"] for r in duplicates if r[0] == 200]
            report["unique_duplicate_numbers"] = len(set(duplicate_numbers))
            large = dict(payload, line_items=[dict(payload["line_items"][0], item_name=f"Fixture item {i}",
                         item_long_description="Synthetic configuration and materials. " * 8) for i in range(60)])
            result = request("/save-quote", "POST", large, cookie, token)
            if result[0] != 200:
                raise RuntimeError("Large PDF fixture save failed")
            large_number = json.loads(result[2])["quote_number"]
            with ThreadPoolExecutor(max_workers=2) as pool:
                pdfs = list(pool.map(lambda _: request(f"/generate-pdf/{large_number}", cookie=cookie), range(2)))
            report["pdf_statuses"] = [r[0] for r in pdfs]
            report["pdf_seconds"] = [r[3] for r in pdfs]
            report["pdf_pages"] = [len(PdfReader(io.BytesIO(r[2])).pages) if r[0] == 200 else 0 for r in pdfs]
        print(json.dumps(report, indent=2))
        return 0 if statuses == [200] * 6 and len(set(numbers)) == 6 and report.get("duplicate_statuses") == [200] * 3 and report.get("unique_duplicate_numbers") == 3 and report.get("pdf_statuses") == [200] * 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
