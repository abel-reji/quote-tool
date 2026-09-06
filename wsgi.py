"""Authenticated web entry point. Database initialization is an explicit CLI step."""
import os

os.environ["QUOTE_TOOL_WEB"] = "1"

from app import app as application, DB_FILE

if not application.config["WEB_MODE"]:
    raise RuntimeError("Refusing to expose a desktop-mode app through WSGI.")
if not DB_FILE.is_file():
    raise RuntimeError("Initialize the private database with manage_web.py init before serving requests.")
