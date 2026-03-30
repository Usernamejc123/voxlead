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

# ── Template Engine ───────────────────────────────────────────────────────────
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
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


# ── Request Handler ───────────────────────────────────────────────────────────

class VoxleadHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str, status: int = 200):
        body = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_redirect(self, url: str):
        self.send_response(302)
        self.send_header("Location", url)
        self.end_headers()

    def _send_static(self, filepath: str):
        ext_map = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
        }
        ext = os.path.splitext(filepath)[1]
        content_type = ext_map.get(ext, "application/octet-stream")
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length else b""

    def _parse_json_body(self) -> dict:
        body = self._read_body()
        return json.loads(body) if body else {}

    def _parse_form_body(self) -> dict:
        body = self._read_body().decode("utf-8")
        return dict(item.split("=", 1) for item in body.split("&") if "=" in item)

    # ── GET routes ────────────────────────────────────────────────────────────

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        try:
            # Static files
            if path.startswith("/static/"):
                safe_path = os.path.normpath(
                    os.path.join(STATIC_DIR, path[len("/static/"):])
                )
                if safe_path.startswith(STATIC_DIR):
                    self._send_static(safe_path)
                else:
                    self.send_response(403)
                    self.end_headers()
                return

            # Homepage
            if path == "/":
                self._send_html(render("landing.html"))
                return

            # Signup / intake form
            if path == "/signup":
                plan = query.get("plan", ["starter"])[0]
                cancelled = query.get("cancelled", [""])[0]
                self._send_html(render("signup.html", selected_plan=plan, cancelled=cancelled))
                return

            # Success page (post-checkout)
            if path == "/success":
                session_id = query.get("session_id", [""])[0]
                plan = query.get("plan", [""])[0]
                name = query.get("name", [""])[0]
                self._send_html(render("success.html", session_id=session_id, plan=plan, name=name))
                return

            # Operator dashboard (protected)
            if path == "/dashboard":
                if require_auth(self):
                    return
                self._send_html(render("dashboard.html"))
                return

            # API: Health check
            if path == "/api/health":
                self._send_json({"status": "ok", "service": "voxlead", "version": "2.0"})
                return

            # API: Dashboard stats (protected)
            if path == "/api/dashboard/stats":
                if require_auth(self):
                    return
                stats = airtable_client.get_dashboard_stats()
                self._send_json(stats)
                return

            # API: List clients (protected)
            if path == "/api/clients":
                if require_auth(self):
                    return
                status_filter = query.get("status", [None])[0]
                clients = airtable_client.list_clients(status_filter=status_filter)
                self._send_json({"records": clients})
                return

            # API: Instantly campaign list/analytics
            if path.startswith("/api/instantly/campaigns"):
                if require_auth(self):
                    return
                parts = path.split("/")
                if len(parts) >= 5 and parts[4] == "analytics":
                    campaign_id = parts[3]
                    analytics = instantly_handler.get_campaign_analytics(campaign_id)
                    self._send_json(analytics)
                else:
                    campaigns = instantly_handler.list_campaigns()
                    self._send_json({"campaigns": campaigns})
                return

            # 404
            self._send_html(
                "<html><body style='background:#080d1a;color:#94a3b8;font-family:sans-serif;text-align:center;padding:4rem'>"
                "<h1 style='color:white'>404</h1><p>Page not found</p>"
                "<a href='/' style='color:#3b82f6'>← Back to homepage</a></body></html>",
                status=404,
            )

        except Exception as e:
            traceback.print_exc()
            self._send_json({"error": str(e)}, status=500)

    # ── POST routes ───────────────────────────────────────────────────────────

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        try:
            # Stripe: Create checkout session
            if path == "/api/checkout":
                content_type = self.headers.get("Content-Type", "")
                if "json" in content_type:
                    data = self._parse_json_body()
                else:
                    from urllib.parse import unquote_plus
                    raw = self._parse_form_body()
                    data = {k: unquote_plus(v) for k, v in raw.items()}

                # Save to Airtable first
                try:
                    _save_client_intake(data)
                except Exception as e:
                    print(f"[Voxlead] Airtable save error: {e}")

                # Create Stripe checkout
                try:
                    session = stripe_handler.create_checkout_session(
                        plan=data.get("plan", "starter"),
                        company_name=data.get("company_name", ""),
                        contact_name=data.get("contact_name", ""),
                        contact_email=data.get("contact_email", ""),
                        what_they_sell=data.get("what_they_sell", ""),
                        target_location=data.get("target_location", ""),
                    )
                    if session.get("url"):
                        self._send_json({"url": session["url"], "id": session.get("id", "")})
                    else:
                        # Stripe not configured — redirect to success
                        self._send_json({"redirect": "/success?plan=" + data.get("plan", "starter")})
                except Exception as stripe_err:
                    # Stripe not configured — just redirect to success
                    print(f"[Voxlead] Stripe error (likely not configured yet): {stripe_err}")
                    self._send_json({"redirect": "/success?plan=" + data.get("plan", "starter")})
                return

            # Stripe: Webhook
            if path == "/api/webhooks/stripe":
                payload = self._read_body()
                sig = self.headers.get("Stripe-Signature", "")
                try:
                    event = stripe_handler.verify_webhook_signature(payload, sig)
                except ValueError as e:
                    self._send_json({"error": str(e)}, status=400)
                    return

                event_type = event.get("type", "")
                if event_type == "checkout.session.completed":
                    record = stripe_handler.handle_checkout_completed(event)
                    self._send_json({"received": True, "record_id": record.get("id", "")})
                else:
                    self._send_json({"received": True, "type": event_type})
                return

            # n8n: Launch campaign (operator approves)
            approve_match = re.match(r"^/api/clients/([a-zA-Z0-9]+)/approve$", path)
            if approve_match:
                if require_auth(self):
                    return
                record_id = approve_match.group(1)
                result = n8n_handler.trigger_campaign(record_id)
                self._send_json(result)
                return

            # n8n: Status callback (n8n calls back with progress updates)
            if path == "/api/webhooks/status":
                data = self._parse_json_body()
                result = n8n_handler.handle_status_callback(data)
                self._send_json(result)
                return

            # Instantly: Reply webhook (reply_received / auto_reply_received)
            if path == "/api/webhooks/instantly":
                data = self._parse_json_body()
                result = instantly_handler.handle_reply_received(data)
                self._send_json(result)
                return

            self._send_json({"error": "Not found"}, status=404)

        except Exception as e:
            traceback.print_exc()
            self._send_json({"error": str(e)}, status=500)

    # ── OPTIONS (CORS) ────────────────────────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Stripe-Signature")
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[Voxlead] {args[0]}" if args else "")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save_client_intake(data: dict) -> dict:
    """Save a new client intake form submission to Airtable."""
    import datetime
    plan = data.get("plan", "starter")
    plan_info = config.PLANS.get(plan, config.PLANS["starter"])

    fields = {
        "Company Name": data.get("company_name", ""),
        "Contact Name": data.get("contact_name", ""),
        "Contact Email": data.get("contact_email", ""),
        "What They Sell": data.get("what_they_sell", ""),
        "Problem Solved": data.get("problem_solved", ""),
        "Unique Value": data.get("unique_value", ""),
        "Target Industry": data.get("target_industry", ""),
        "Target Titles": data.get("target_titles", ""),
        "Target Location": data.get("target_location", ""),
        "Company Size": data.get("company_size", ""),
        "Deal Size": data.get("deal_size", ""),
        "CTA Type": data.get("cta_type", ""),
        "Calendly Link": data.get("calendly_link", ""),
        "Exclusions": data.get("exclusions", ""),
        "Additional Notes": data.get("additional_notes", ""),
        "Website": data.get("website", ""),
        "Package": plan,
        "Status": "pending_review",
        "Submitted At": datetime.datetime.utcnow().isoformat() + "Z",
    }
    return airtable_client.create_client(fields)


# ── Main ──────────────────────────────────────────────────────────────────────

def run():
    server = HTTPServer(("0.0.0.0", config.PORT), VoxleadHandler)
    print(f"[Voxlead] Server running on http://localhost:{config.PORT}")
    print(f"[Voxlead] Dashboard: http://localhost:{config.PORT}/dashboard")
    print(f"[Voxlead]   Login: admin / {config.DASHBOARD_PASSWORD}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Voxlead] Shutting down.")
        server.server_close()


if __name__ == "__main__":
    run()
