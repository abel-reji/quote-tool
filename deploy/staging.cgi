#!/home3/finvestc/quote-tool-web/.venv/bin/python
"""Opt-in reference CGI adapter; owner accepted its production-use limitation."""
import os
import sys

# Only this adapter and .htaccess belong in the public document root.
sys.path.insert(0, "/home3/finvestc/quote-tool-web")
os.environ["QUOTE_TOOL_CONFIG"] = "/home3/finvestc/quote-tool-private/web-config.json"
os.environ["SCRIPT_NAME"] = ""

if os.path.exists("/home3/finvestc/quote-tool-private/maintenance.flag"):
    print("Status: 503 Service Unavailable\r\nContent-Type: text/plain\r\nRetry-After: 60\r\nCache-Control: no-store\r\n\r\nQuote Tool is briefly unavailable for maintenance.")
    raise SystemExit(0)

from wsgi import application
from app import WEB_CONFIG

if WEB_CONFIG.get("allow_reference_cgi") is not True:
    raise RuntimeError("Reference CGI is disabled. Explicit owner opt-in is required.")

from wsgiref.handlers import CGIHandler

CGIHandler().run(application)
