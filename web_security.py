"""Opt-in single-user security; desktop launches do not require credentials."""

from datetime import timedelta
from contextlib import closing
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

from flask import g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash
from werkzeug.exceptions import SecurityError


def load_web_config():
    mode = os.environ.get("QUOTE_TOOL_WEB", "0")
    if mode not in {"0", "1"}:
        raise RuntimeError("QUOTE_TOOL_WEB must be 0 or 1.")
    if mode == "0":
        return None
    filename = Path(os.environ.get("QUOTE_TOOL_CONFIG", ""))
    if not filename.is_absolute() or not filename.is_file():
        raise RuntimeError("Web mode requires an absolute QUOTE_TOOL_CONFIG file path.")
    config = json.loads(filename.read_text(encoding="utf-8"))
    for key in ("secret_key", "username", "password_hash", "storage_root", "public_root", "host"):
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise RuntimeError(f"Missing web configuration: {key}")
    if len(config["secret_key"]) < 32:
        raise RuntimeError("Web secret_key must contain at least 32 characters.")
    if not config["password_hash"].startswith(("scrypt:", "pbkdf2:sha256:")):
        raise RuntimeError("Use a Werkzeug password hash, never a plaintext password.")
    if any(char in config["host"] for char in "/\\:@* \t\r\n"):
        raise RuntimeError("host must be a hostname without a scheme, port or wildcard.")
    storage, public = Path(config["storage_root"]), Path(config["public_root"])
    if not storage.is_absolute() or not public.is_absolute():
        raise RuntimeError("Storage and public roots must be absolute paths.")
    storage, public = storage.resolve(), public.resolve()
    if storage.is_relative_to(public) or public.is_relative_to(storage):
        raise RuntimeError("Private storage and public directories must not overlap.")
    if filename.resolve().is_relative_to(public):
        raise RuntimeError("The credentials file must be outside the public directory.")
    config["storage_root"], config["public_root"] = storage, public
    return config


def install_web_security(app, config):
    app.config["WEB_MODE"] = config is not None
    if config is None:
        @app.context_processor
        def desktop_context():
            return {"web_mode": False, "csrf_token": lambda: "", "csp_nonce": ""}
        return

    app.config.update(
        SECRET_KEY=config["secret_key"], DEBUG=False,
        TRUSTED_HOSTS=[config["host"]],
        SESSION_COOKIE_NAME="__Host-quote_session",
        SESSION_COOKIE_SECURE=True, SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_PATH="/",
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_REFRESH_EACH_REQUEST=False,
        MAX_CONTENT_LENGTH=25 * 1024 * 1024, MAX_FORM_PARTS=100,
    )
    # Changing credentials invalidates existing signed login sessions.
    account_tag = hmac.new(config["secret_key"].encode(),
        (config["username"] + "\0" + config["password_hash"]).encode(), hashlib.sha256).hexdigest()
    throttle_path = config["storage_root"] / "login-attempts.sqlite3"

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    def logged_in():
        return hmac.compare_digest(str(session.get("account", "")), account_tag)

    def reserve_login_attempt():
        # Account-wide throttling persists across CGI workers; no trust in client IP headers.
        with closing(sqlite3.connect(throttle_path, timeout=10)) as conn, conn:
            conn.execute("CREATE TABLE IF NOT EXISTS attempts (at REAL NOT NULL)")
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM attempts WHERE at < ?", (time.time() - 900,))
            if conn.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] >= 10:
                return False
            conn.execute("INSERT INTO attempts VALUES (?)", (time.time(),))
        return True

    @app.before_request
    def protect_web_request():
        g.csp_nonce = secrets.token_urlsafe(24)
        if isinstance(request.routing_exception, SecurityError):
            raise request.routing_exception
        if not request.is_secure:
            return jsonify(status="error", message="HTTPS is required."), 400
        if request.endpoint not in {"web_login", "static"} and not logged_in():
            if request.method in {"GET", "HEAD"} and request.accept_mimetypes.best == "text/html":
                return redirect(url_for("web_login"))
            return jsonify(status="error", message="Please sign in again."), 401
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            expected = session.get("csrf", "")
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token", "")
            if not expected or not hmac.compare_digest(str(expected).encode(), str(supplied).encode()):
                return jsonify(status="error", message="Session expired. Reload the page and try again."), 400

    @app.context_processor
    def web_context():
        return {"web_mode": True, "web_signed_in": logged_in(),
                "csrf_token": csrf_token, "csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        nonce = getattr(g, "csp_nonce", "")
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; " + f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if response.status_code >= 500:
            app.logger.error("Request failed: %s %s", request.method, request.path)
            response.set_data('{"status":"error","message":"Server error. Check the private server log."}')
            response.content_type = "application/json"
        return response

    @app.route("/login", methods=["GET", "POST"], endpoint="web_login")
    def login():
        error, status = None, 200
        if request.method == "POST":
            if not reserve_login_attempt():
                return render_template("login.html", error="Too many attempts. Try again in 15 minutes."), 429, {"Retry-After": "900"}
            password = request.form.get("password", "")
            valid_password = len(password) <= 1024 and check_password_hash(config["password_hash"], password)
            valid_user = hmac.compare_digest(request.form.get("username", "").encode(), config["username"].encode())
            if valid_user and valid_password:
                with closing(sqlite3.connect(throttle_path, timeout=10)) as conn, conn:
                    conn.execute("DELETE FROM attempts")
                session.clear()
                session["account"] = account_tag
                session.permanent = True
                csrf_token()
                return redirect(url_for("landing_page"))
            error, status = "Incorrect username or password.", 401
        return render_template("login.html", error=error), status

    @app.post("/logout", endpoint="web_logout")
    def logout():
        session.clear()
        return redirect(url_for("web_login"))
