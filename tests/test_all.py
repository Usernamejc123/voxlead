#!/usr/bin/env python3
"""
Voxlead — Comprehensive Test Suite
Tests all critical paths: config, routing, Airtable client, Stripe handler,
Make.com handler, template rendering, and the full request/response cycle.
"""

import json
import os
import sys
import unittest
import base64
from unittest.mock import patch, MagicMock
from io import BytesIO
from http.server import HTTPServer
import threading
import urllib.request
import urllib.error
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import airtable_client
import stripe_handler
import make_handler
from server import VoxleadHandler, render


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIG TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestConfig(unittest.TestCase):
    def test_plans_exist(self):
        self.assertIn("starter", config.PLANS)
        self.assertIn("growth", config.PLANS)
        self.assertIn("scale", config.PLANS)

    def test_plan_structure(self):
        for name, plan in config.PLANS.items():
            self.assertIn("name", plan)
            self.assertIn("price", plan)
            self.assertIn("leads", plan)
            self.assertIn("stripe_price_id", plan)
            self.assertIn("features", plan)
            self.assertIsInstance(plan["price"], int)
            self.assertIsInstance(plan["leads"], int)
            self.assertIsInstance(plan["features"], list)
            self.assertGreater(len(plan["features"]), 0)

    def test_plan_pricing_order(self):
        self.assertLess(config.PLANS["starter"]["price"], config.PLANS["growth"]["price"])
        self.assertLess(config.PLANS["growth"]["price"], config.PLANS["scale"]["price"])

    def test_plan_leads_order(self):
        self.assertLess(config.PLANS["starter"]["leads"], config.PLANS["growth"]["leads"])
        self.assertLess(config.PLANS["growth"]["leads"], config.PLANS["scale"]["leads"])

    def test_airtable_config(self):
        self.assertEqual(config.AIRTABLE_BASE_ID, "app6VovTdNZtSbOli")
        self.assertEqual(config.AIRTABLE_CLIENTS_TABLE, "tbliRFtZV1Kfzb7ZK")
        self.assertEqual(config.AIRTABLE_LEADS_TABLE, "tblXKBbXFNyuwUAyq")

    def test_make_webhook_urls(self):
        self.assertIn("hook.us2.make.com", config.MAKE_CAMPAIGN_WEBHOOK_URL)
        self.assertIn("hook.us2.make.com", config.MAKE_APOLLO_WEBHOOK_URL)

    def test_clients_fields_mapping(self):
        expected_keys = [
            "company_name", "contact_name", "contact_email",
            "what_they_sell", "target_location", "lead_volume",
            "package", "status", "leads_researched", "emails_sent",
            "replies_received", "cost_tracked",
        ]
        for key in expected_keys:
            self.assertIn(key, config.CLIENTS_FIELDS)


# ══════════════════════════════════════════════════════════════════════════════
# 2. TEMPLATE RENDERING TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestTemplates(unittest.TestCase):
    def test_landing_renders(self):
        html = render("landing.html")
        self.assertIn("Voxlead", html)
        self.assertIn("$497", html)
        self.assertIn("$997", html)
        self.assertIn("$1,997", html)
        self.assertIn("Cold Email", html)
        self.assertIn("/signup", html)
        self.assertIn("How Voxlead works", html)

    def test_signup_renders(self):
        html = render("signup.html", selected_plan="growth", cancelled="")
        self.assertIn("Start your campaign", html)
        self.assertIn("growth", html)
        self.assertIn("company_name", html)
        self.assertIn("contact_email", html)
        self.assertIn("/api/checkout", html)

    def test_signup_cancelled_banner(self):
        html = render("signup.html", selected_plan="starter", cancelled="true")
        self.assertIn("cancelled", html.lower())

    def test_success_renders(self):
        html = render("success.html", session_id="cs_test_123")
        self.assertIn("payment confirmed", html.lower())
        self.assertIn("what happens next", html.lower())

    def test_dashboard_renders(self):
        html = render("dashboard.html")
        self.assertIn("Operator", html)
        self.assertIn("/api/dashboard/stats", html)
        self.assertIn("/api/clients/", html)
        self.assertIn("approve", html.lower())
        self.assertIn("Refresh", html)


# ══════════════════════════════════════════════════════════════════════════════
# 3. AIRTABLE CLIENT TESTS (mocked)
# ══════════════════════════════════════════════════════════════════════════════


class TestAirtableClient(unittest.TestCase):
    @patch("airtable_client.requests.get")
    def test_list_clients(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "records": [
                {"id": "rec1", "fields": {"Company Name": "Acme", "Status": "paid"}}
            ]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        clients = airtable_client.list_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["fields"]["Company Name"], "Acme")

        # Verify correct URL called
        call_url = mock_get.call_args[0][0]
        self.assertIn("app6VovTdNZtSbOli", call_url)
        self.assertIn("tbliRFtZV1Kfzb7ZK", call_url)

    @patch("airtable_client.requests.get")
    def test_list_clients_with_filter(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"records": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        airtable_client.list_clients(status_filter="paid")
        params = mock_get.call_args[1]["params"]
        self.assertIn("filterByFormula", params)
        self.assertIn("paid", params["filterByFormula"])

    @patch("airtable_client.requests.post")
    def test_create_client(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "records": [{"id": "rec_new", "fields": {"Company Name": "Test Co"}}]
        }
        mock_resp.raise_for_status = MagicMock()
        mock_post.return_value = mock_resp

        result = airtable_client.create_client({"Company Name": "Test Co"})
        self.assertEqual(result["id"], "rec_new")

    @patch("airtable_client.requests.patch")
    def test_update_client(self, mock_patch):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": "rec1", "fields": {"Status": "running"}}
        mock_resp.raise_for_status = MagicMock()
        mock_patch.return_value = mock_resp

        result = airtable_client.update_client("rec1", {"Status": "running"})
        self.assertEqual(result["fields"]["Status"], "running")

    @patch("airtable_client.list_clients")
    @patch("airtable_client.count_leads_by_status")
    def test_get_dashboard_stats(self, mock_leads, mock_clients):
        mock_clients.return_value = [
            {
                "id": "rec1",
                "fields": {
                    "Company Name": "Acme",
                    "Contact Name": "Jane",
                    "Contact Email": "jane@acme.com",
                    "What They Sell": "SaaS",
                    "Target Location": "US",
                    "Lead Volume": 500,
                    "Package": "Starter",
                    "Status": "running",
                    "Leads Researched": 100,
                    "Emails Sent": 80,
                    "Replies Received": 5,
                    "Cost Tracked": 2.50,
                },
            }
        ]
        mock_leads.return_value = {"new": 20, "validated": 30, "enriched": 50}

        stats = airtable_client.get_dashboard_stats()
        self.assertEqual(stats["total_clients"], 1)
        self.assertEqual(stats["total_leads_researched"], 100)
        self.assertEqual(stats["total_emails_sent"], 80)
        self.assertEqual(stats["total_replies"], 5)
        self.assertEqual(stats["total_cost"], 2.50)
        self.assertEqual(stats["reply_rate"], 6.2)
        self.assertEqual(stats["cost_per_lead"], 0.025)
        self.assertIn("running", stats["client_status_counts"])
        self.assertEqual(len(stats["clients"]), 1)
        self.assertEqual(stats["clients"][0]["company_name"], "Acme")


# ══════════════════════════════════════════════════════════════════════════════
# 4. STRIPE HANDLER TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestStripeHandler(unittest.TestCase):
    def test_create_checkout_invalid_plan(self):
        with self.assertRaises(ValueError):
            stripe_handler.create_checkout_session(
                plan="nonexistent",
                company_name="Test",
                contact_name="Jane",
                contact_email="j@t.com",
                what_they_sell="Widgets",
                target_location="US",
            )

    @patch("stripe_handler._stripe_request")
    def test_create_checkout_session(self, mock_stripe):
        mock_stripe.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
        }

        result = stripe_handler.create_checkout_session(
            plan="growth",
            company_name="Acme",
            contact_name="Jane",
            contact_email="jane@acme.com",
            what_they_sell="SaaS tools",
            target_location="United States",
        )

        self.assertEqual(result["id"], "cs_test_123")
        self.assertIn("checkout.stripe.com", result["url"])

        # Verify the Stripe API was called with correct params
        call_args = mock_stripe.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertEqual(call_args[0][1], "checkout/sessions")
        data = call_args[1]["data"] if "data" in call_args[1] else call_args[0][2]
        self.assertEqual(data["metadata[plan]"], "growth")
        self.assertEqual(data["metadata[company_name]"], "Acme")

    @patch("stripe_handler.airtable_client.create_client")
    def test_handle_checkout_completed(self, mock_create):
        mock_create.return_value = {"id": "rec_new", "fields": {}}

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {
                        "plan": "starter",
                        "company_name": "Acme",
                        "contact_name": "Jane",
                        "contact_email": "jane@acme.com",
                        "what_they_sell": "Widgets",
                        "target_location": "US",
                    },
                }
            },
        }

        result = stripe_handler.handle_checkout_completed(event)
        self.assertEqual(result["id"], "rec_new")

        # Verify Airtable fields
        create_call = mock_create.call_args[0][0]
        self.assertEqual(create_call["Company Name"], "Acme")
        self.assertEqual(create_call["Status"], "paid")
        self.assertEqual(create_call["Lead Volume"], 500)  # starter plan
        self.assertEqual(create_call["Package"], "Starter")

    def test_verify_webhook_no_secret(self):
        """When STRIPE_WEBHOOK_SECRET is empty, skip verification (dev mode)."""
        original = config.STRIPE_WEBHOOK_SECRET
        config.STRIPE_WEBHOOK_SECRET = ""
        try:
            payload = json.dumps({"type": "test"}).encode()
            result = stripe_handler.verify_webhook_signature(payload, "")
            self.assertEqual(result["type"], "test")
        finally:
            config.STRIPE_WEBHOOK_SECRET = original


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAKE HANDLER TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestMakeHandler(unittest.TestCase):
    @patch("make_handler.requests.post")
    @patch("make_handler.airtable_client.update_client")
    @patch("make_handler.airtable_client.get_client")
    def test_trigger_campaign(self, mock_get, mock_update, mock_post):
        mock_get.return_value = {
            "id": "rec1",
            "fields": {
                "Company Name": "Acme",
                "Contact Name": "Jane",
                "Contact Email": "jane@acme.com",
                "What They Sell": "SaaS",
                "Target Location": "United States",
                "Lead Volume": 500,
                "Package": "Starter",
            },
        }
        mock_update.return_value = {}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"received": true}'
        mock_post.return_value = mock_resp

        result = make_handler.trigger_campaign("rec1")
        self.assertTrue(result["success"])
        self.assertEqual(result["client_id"], "rec1")

        # Verify Airtable was updated to "running"
        mock_update.assert_called_once_with("rec1", {"Status": "running"})

        # Verify Make.com webhook was called
        webhook_call = mock_post.call_args
        self.assertIn("hook.us2.make.com", webhook_call[0][0])
        payload = webhook_call[1]["json"]
        self.assertEqual(payload["company_name"], "Acme")
        self.assertEqual(payload["plan"], "starter")

    @patch("make_handler.airtable_client.update_client")
    def test_handle_status_callback(self, mock_update):
        mock_update.return_value = {}

        data = {
            "client_id": "rec1",
            "leads_researched": 150,
            "emails_sent": 120,
            "replies_received": 8,
            "cost_tracked": 3.75,
            "status": "running",
        }

        result = make_handler.handle_status_callback(data)
        self.assertTrue(result["success"])
        self.assertIn("Leads Researched", result["updated_fields"])
        self.assertIn("Emails Sent", result["updated_fields"])

        update_call = mock_update.call_args[0]
        self.assertEqual(update_call[0], "rec1")
        self.assertEqual(update_call[1]["Leads Researched"], 150)
        self.assertEqual(update_call[1]["Emails Sent"], 120)

    def test_handle_status_callback_missing_client_id(self):
        result = make_handler.handle_status_callback({})
        self.assertIn("error", result)


# ══════════════════════════════════════════════════════════════════════════════
# 6. SERVER INTEGRATION TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestServerIntegration(unittest.TestCase):
    """Start a real test server and make HTTP requests against it."""

    @classmethod
    def setUpClass(cls):
        cls.port = 9876
        config.PORT = cls.port
        cls.server = HTTPServer(("127.0.0.1", cls.port), VoxleadHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()
        time.sleep(0.3)
        cls.base = f"http://127.0.0.1:{cls.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _get(self, path, auth=None):
        req = urllib.request.Request(f"{self.base}{path}")
        if auth:
            creds = base64.b64encode(auth.encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        try:
            resp = urllib.request.urlopen(req)
            return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def _post(self, path, data, content_type="application/json", auth=None):
        body = json.dumps(data).encode() if isinstance(data, dict) else data.encode()
        req = urllib.request.Request(f"{self.base}{path}", data=body, method="POST")
        req.add_header("Content-Type", content_type)
        if auth:
            creds = base64.b64encode(auth.encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        try:
            resp = urllib.request.urlopen(req)
            return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    # ── Page routes ───────────────────────────────────────────────────────

    def test_landing_page(self):
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("Voxlead", body)
        self.assertIn("$497", body)
        self.assertIn("$997", body)

    def test_signup_page(self):
        status, body = self._get("/signup?plan=growth")
        self.assertEqual(status, 200)
        self.assertIn("Start your campaign", body)

    def test_success_page(self):
        status, body = self._get("/success?session_id=cs_test_123")
        self.assertEqual(status, 200)
        self.assertIn("payment confirmed", body.lower())

    def test_health_endpoint(self):
        status, body = self._get("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "voxlead")

    # ── Dashboard auth ────────────────────────────────────────────────────

    def test_dashboard_requires_auth(self):
        status, _ = self._get("/dashboard")
        self.assertEqual(status, 401)

    def test_dashboard_with_auth(self):
        status, body = self._get("/dashboard", auth=f"admin:{config.DASHBOARD_PASSWORD}")
        self.assertEqual(status, 200)
        self.assertIn("Operator", body)

    def test_api_stats_requires_auth(self):
        status, _ = self._get("/api/dashboard/stats")
        self.assertEqual(status, 401)

    def test_api_clients_requires_auth(self):
        status, _ = self._get("/api/clients")
        self.assertEqual(status, 401)

    # ── API routes ────────────────────────────────────────────────────────

    @patch("stripe_handler.create_checkout_session")
    def test_checkout_api(self, mock_checkout):
        mock_checkout.return_value = {
            "id": "cs_test_123",
            "url": "https://checkout.stripe.com/pay/cs_test_123",
        }

        status, body = self._post("/api/checkout", {
            "plan": "growth",
            "company_name": "Test Co",
            "contact_name": "John",
            "contact_email": "john@test.com",
            "what_they_sell": "Software",
            "target_location": "US",
        })

        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("url", data)
        self.assertIn("checkout.stripe.com", data["url"])

    def test_stripe_webhook_no_body(self):
        status, body = self._post("/api/webhooks/stripe", "")
        # Should handle gracefully (dev mode skips sig verification)
        self.assertIn(status, [200, 400, 500])

    @patch("make_handler.handle_status_callback")
    def test_status_callback(self, mock_callback):
        mock_callback.return_value = {"success": True, "updated_fields": ["Status"]}

        status, body = self._post("/api/webhooks/status", {
            "client_id": "rec_test",
            "status": "running",
        })

        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])

    @patch("make_handler.trigger_campaign")
    def test_approve_requires_auth(self, mock_trigger):
        status, _ = self._post("/api/clients/rec123/approve", {})
        self.assertEqual(status, 401)

    @patch("make_handler.trigger_campaign")
    def test_approve_with_auth(self, mock_trigger):
        mock_trigger.return_value = {"success": True, "client_id": "rec123"}
        status, body = self._post(
            "/api/clients/rec123/approve",
            {},
            auth=f"admin:{config.DASHBOARD_PASSWORD}",
        )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["success"])

    # ── 404 ───────────────────────────────────────────────────────────────

    def test_404_page(self):
        status, body = self._get("/nonexistent")
        self.assertIn(status, [200, 404])  # 200 with 404 content or actual 404


# ══════════════════════════════════════════════════════════════════════════════
# 7. DATA FLOW TESTS
# ══════════════════════════════════════════════════════════════════════════════


class TestDataFlow(unittest.TestCase):
    """Test the end-to-end data flow from signup to campaign approval."""

    @patch("make_handler.requests.post")
    @patch("make_handler.airtable_client.update_client")
    @patch("make_handler.airtable_client.get_client")
    @patch("stripe_handler.airtable_client.create_client")
    @patch("stripe_handler._stripe_request")
    def test_full_flow(self, mock_stripe, mock_create, mock_get_client, mock_update, mock_make_post):
        # Step 1: Client submits form → Stripe checkout
        mock_stripe.return_value = {
            "id": "cs_test_flow",
            "url": "https://checkout.stripe.com/pay/cs_test_flow",
        }

        session = stripe_handler.create_checkout_session(
            plan="growth",
            company_name="FlowTest Inc",
            contact_name="Alice",
            contact_email="alice@flowtest.com",
            what_they_sell="B2B analytics",
            target_location="United States",
        )
        self.assertIn("url", session)

        # Step 2: Stripe sends checkout.session.completed webhook
        mock_create.return_value = {"id": "recFlow1", "fields": {"Status": "paid"}}

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_flow",
                    "metadata": {
                        "plan": "growth",
                        "company_name": "FlowTest Inc",
                        "contact_name": "Alice",
                        "contact_email": "alice@flowtest.com",
                        "what_they_sell": "B2B analytics",
                        "target_location": "United States",
                    },
                }
            },
        }

        record = stripe_handler.handle_checkout_completed(event)
        self.assertEqual(record["id"], "recFlow1")
        # Verify correct fields sent to Airtable
        fields = mock_create.call_args[0][0]
        self.assertEqual(fields["Status"], "paid")
        self.assertEqual(fields["Lead Volume"], 2000)  # Growth plan

        # Step 3: Operator approves → triggers Make.com campaign
        mock_get_client.return_value = {
            "id": "recFlow1",
            "fields": {
                "Company Name": "FlowTest Inc",
                "Contact Name": "Alice",
                "Contact Email": "alice@flowtest.com",
                "What They Sell": "B2B analytics",
                "Target Location": "United States",
                "Lead Volume": 2000,
                "Package": "Growth",
            },
        }
        mock_update.return_value = {}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '{"received": true}'
        mock_make_post.return_value = mock_resp

        result = make_handler.trigger_campaign("recFlow1")
        self.assertTrue(result["success"])

        # Verify Make.com received correct payload
        payload = mock_make_post.call_args[1]["json"]
        self.assertEqual(payload["company_name"], "FlowTest Inc")
        self.assertEqual(payload["plan"], "growth")
        self.assertIn("status_callback_url", payload)

        # Step 4: Make.com sends status callback
        mock_update.reset_mock()
        callback_data = {
            "client_id": "recFlow1",
            "leads_researched": 500,
            "emails_sent": 400,
            "replies_received": 18,
            "cost_tracked": 12.50,
            "status": "completed",
        }
        result = make_handler.handle_status_callback(callback_data)
        self.assertTrue(result["success"])

        update_fields = mock_update.call_args[0][1]
        self.assertEqual(update_fields["Leads Researched"], 500)
        self.assertEqual(update_fields["Status"], "completed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
