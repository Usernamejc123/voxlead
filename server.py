#!/usr/bin/env python3
"""
Voxlead — Main Server
Operator dashboard + Instantly-powered lead pipeline.
"""

import base64
import csv
import io
import json
import os
import re
import sys
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import instantly
import claude_service
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True)


def render(name, **ctx):
    return jinja_env.get_template(name).render(config=config, **ctx)


# ── Auth ──────────────────────────────────────────────────────────────────────

def _check_auth(handler) -> bool:
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(auth[6:]).decode("utf-8")
        user, pw = decoded.split(":", 1)
        return user == "admin" and pw == config.DASHBOARD_PASSWORD
    except Exception:
        return False


def _require_auth(handler) -> bool:
    if not _check_auth(handler):
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="Voxlead"')
        handler.send_header("Content-Type", "text/plain")
        handler.end_headers()
        handler.wfile.write(b"Login required")
        return True
    return False


# ── Handler ───────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def _json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html, status=200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _json_body(self):
        return json.loads(self._body() or b"{}")

    # ── GET ───────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            if path == "/":
                self._html(render("landing.html"))
                return

            if path == "/dashboard":
                if _require_auth(self):
                    return
                self._html(render("dashboard.html"))
                return

            if path == "/api/health":
                self._json({"status": "ok"})
                return

            # List campaigns from Instantly
            if path == "/api/campaigns":
                if _require_auth(self):
                    return
                result = instantly.list_campaigns()
                self._json(result)
                return

            # Campaign analytics
            m = re.match(r"^/api/campaigns/([^/]+)/analytics$", path)
            if m:
                if _require_auth(self):
                    return
                result = instantly.get_analytics(m.group(1))
                self._json(result)
                return

            self._json({"error": "not found"}, 404)

        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    # ── POST ──────────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            # Create a campaign
            if path == "/api/campaigns":
                if _require_auth(self):
                    return
                data = self._json_body()
                name = data.get("name", "New Campaign")
                result = instantly.create_campaign(name)
                self._json(result)
                return

            # Launch a campaign
            m = re.match(r"^/api/campaigns/([^/]+)/launch$", path)
            if m:
                if _require_auth(self):
                    return
                result = instantly.launch_campaign(m.group(1))
                self._json(result)
                return

            # Pause a campaign
            m = re.match(r"^/api/campaigns/([^/]+)/pause$", path)
            if m:
                if _require_auth(self):
                    return
                result = instantly.pause_campaign(m.group(1))
                self._json(result)
                return

            # Upload leads: CSV text + campaign_id → Claude icebreakers → Instantly
            if path == "/api/upload-leads":
                if _require_auth(self):
                    return
                data = self._json_body()
                campaign_id = data.get("campaign_id", "")
                csv_text = data.get("csv", "")

                if not campaign_id or not csv_text:
                    self._json({"error": "campaign_id and csv required"}, 400)
                    return

                # Parse CSV
                reader = csv.DictReader(io.StringIO(csv_text))
                leads = []
                for row in reader:
                    # Normalize column names (lowercase, strip spaces)
                    row = {k.strip().lower(): v.strip() for k, v in row.items()}

                    email = (
                        row.get("email") or row.get("email address") or ""
                    ).strip()
                    if not email or "@" not in email:
                        continue

                    lead = {
                        "email": email,
                        "first_name": row.get("first_name") or row.get("first name") or "",
                        "last_name": row.get("last_name") or row.get("last name") or "",
                        "company": row.get("company") or row.get("company name") or "",
                        "title": row.get("title") or row.get("job title") or "",
                        "industry": row.get("industry") or "",
                    }

                    # Generate icebreaker with Claude
                    lead["personalization"] = claude_service.generate_icebreaker(lead)
                    leads.append(lead)

                if not leads:
                    self._json({"error": "No valid leads found in CSV"}, 400)
                    return

                # Push to Instantly
                result = instantly.add_leads(campaign_id, leads)
                self._json({
                    "leads_processed": len(leads),
                    "instantly_response": result,
                })
                return

            self._json({"error": "not found"}, 404)

        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[Voxlead] {self.address_string()} {args[0] if args else ''}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    port = config.PORT
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Voxlead] Running on port {port}")
    print(f"[Voxlead] Dashboard → http://localhost:{port}/dashboard  (admin / {config.DASHBOARD_PASSWORD})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    run()
