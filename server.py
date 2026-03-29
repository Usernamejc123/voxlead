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


# — Auth ————————————————————————————————————————————————————————
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


# — Handler ————————————————————————————————————————————————————————
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

    # — GET ——————————————————————————————————————————————————————
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/":
                self._html(render("landing.html"))
                return
            if path == "/dashboard":
                if _require_auth(self): return
                _dash = render("dashboard.html")
                _js_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "dashboard.js")
                if os.path.exists(_js_path):
                    with open(_js_path, encoding="utf-8") as _jf:
                        _js = _jf.read()
                    _dash = _dash.replace("</body>", "<script>" + _js + "</script></body>", 1)
                self._html(_dash)
                return
            if path == "/signup":
                plan = parse_qs(parsed.query).get("plan", ["starter"])[0]
                cancelled = parse_qs(parsed.query).get("cancelled", [""])[0]
                self._html(render("signup.html", selected_plan=plan, cancelled=cancelled))
                return
            if path == "/success":
                session_id = parse_qs(parsed.query).get("session_id", [""])[0]
                self._html(render("success.html", session_id=session_id))
                return
            if path == "/api/health":
                self._json({"status": "ok"})
                return
            if path == "/api/campaigns":
                if _require_auth(self): return
                result = instantly.list_campaigns()
                self._json(result)
                return
            m = re.match(r"^/api/campaigns/([^/]+)/analytics$", path)
            if m:
                if _require_auth(self): return
                result = instantly.get_analytics(m.group(1))
                self._json(result)
                return
            self._json({"error": "not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    # — POST ——————————————————————————————————————————————————————
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/api/campaigns":
                if _require_auth(self): return
                data = self._json_body()
                name = data.get("name", "New Campaign")
                result = instantly.create_campaign(name)
                self._json(result)
                return
            m = re.match(r"^/api/campaigns/([^/]+)/launch$", path)
            if m:
                if _require_auth(self): return
                result = instantly.set_campaign_status(m.group(1), 1)
                self._json(result)
                return
            m = re.match(r"^/api/campaigns/([^/]+)/pause$", path)
            if m:
                if _require_auth(self): return
                result = instantly.set_campaign_status(m.group(1), 2)
                self._json(result)
                return
            if path == "/api/upload-leads":
                if _require_auth(self): return
                data = self._json_body()
                campaign_id = data.get("campaign_id", "")
                csv_text = data.get("csv", "")
                if not campaign_id or not csv_text:
                    self._json({"error": "campaign_id and csv required"}, 400)
                    return
                reader = csv.DictReader(io.StringIO(csv_text))
                leads = []
                for row in reader:
                    icebreaker = claude_service.generate_icebreaker(row)
                    leads.append({
                        "email": row.get("email", ""),
                        "first_name": row.get("first_name", ""),
                        "last_name": row.get("last_name", ""),
                        "company_name": row.get("company", ""),
                        "personalization": icebreaker,
                        "skip_if_in_workspace": True,
                    })
                result = instantly.upload_leads(campaign_id, leads)
                self._json({"uploaded": len(leads), "result": result})
                return
            if path == "/api/checkout":
                data = self._json_body()
                import stripe_handler as sh
                session = sh.create_checkout_session(
                    plan=data.get("plan", "starter"),
                    company_name=data.get("company_name", ""),
                    contact_name=data.get("contact_name", ""),
                    contact_email=data.get("contact_email", ""),
                    what_they_sell=data.get("what_they_sell", ""),
                    target_location=data.get("target_location", ""),
                )
                self._json({"url": session.get("url", ""), "id": session.get("id", "")})
                return
            self._json({"error": "not found"}, 404)
        except Exception as e:
            traceback.print_exc()
            self._json({"error": str(e)}, 500)

    def log_message(self, fmt, *args):
        pass


def run():
    port = int(os.environ.get("PORT", getattr(config, "PORT", 8000)))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[Voxlead] Running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
