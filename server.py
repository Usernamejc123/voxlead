#!/usr/bin/env python3
"""
Voxlead — Main HTTP Server
Serves the client website, operator dashboard, and all API routes.
"""

import json
import os
import re
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import base64

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import airtable_client
import stripe_handler
import n8n_handler
import instantly_handler

from jinja2 import Environment, FileSystemLoader

# ── Template Engine ───────────────────────────────────────────────────────────LEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


def render(template_name: str, **ctx) -> str:
    tmpl = jinja_env.get_template(template_name)
    return tmpl.render(config=config, **ctx)


# ── Auth Helper ───────────────────────────────────────────────────────────────

def check_dashboard_auth(handler) -> bool:
    """Check Basic auth for dashboard. Returns True if authenticated."""
    auth_header = handler.headers.get("Authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username == "admin" and password == config.DASHBOARD_PASSWORD
    except Exception:
        return False


def require_auth(handler) -> bool:
    """Send 401 if not authenticated. Returns True if auth failed (caller should return)."""
    if not check_dashboard_auth(handler):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="Voxlead Dashboard"')
        handler.send_header("Content-Type", "text/plain")
        handler.end_headers()
        handler.wfile.write(b"Authentication required")
        return True
    return False
