"""
Voxlead Configuration — All environment variables and constants.

Required environment variables:
  STRIPE_SECRET_KEY          - Stripe secret key (sk_test_... or sk_live_...)
  STRIPE_WEBHOOK_SECRET      - Stripe webhook signing secret (whsec_...)
  STRIPE_PRICE_STARTER       - Stripe Price ID for Starter plan ($497/mo)
  STRIPE_PRICE_GROWTH        - Stripe Price ID for Growth plan ($997/mo)
  STRIPE_PRICE_ELITE         - Stripe Price ID for Elite plan ($1,997/mo)
  AIRTABLE_API_KEY           - Airtable personal access token (pat...)
  AIRTABLE_BASE_ID           - Airtable base ID (app...)
  N8N_CAMPAIGN_WEBHOOK_URL   - n8n webhook URL to trigger campaign pipeline
  N8N_REPLY_WEBHOOK_URL      - n8n webhook URL for hot-lead reply handling
  INSTANTLY_API_KEY          - Instantly.ai API v2 key
  ANTHROPIC_API_KEY          - Claude AI key (for personalization + reply classification)
  DASHBOARD_PASSWORD         - Password to access operator dashboard
  APP_URL                    - Public URL of the app (https://yourdomain.com)
  PORT                       - Server port (default 3000)
"""

import os

# ── Stripe ────────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_STARTER = os.environ.get("STRIPE_PRICE_STARTER", "price_starter_placeholder")
STRIPE_PRICE_GROWTH = os.environ.get("STRIPE_PRICE_GROWTH", "price_growth_placeholder")
STRIPE_PRICE_ELITE = os.environ.get("STRIPE_PRICE_ELITE", "price_elite_placeholder")

# ── Airtable ──────────────────────────────────────────────────────────────────
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "app6VovTdNZtSbOli")
AIRTABLE_CLIENTS_TABLE = "tbliRFtZV1Kfzb7ZK"
AIRTABLE_LEADS_TABLE = "tblXKBbXFNyuwUAyq"

# ── n8n (replaces Make.com) ───────────────────────────────────────────────────
N8N_CAMPAIGN_WEBHOOK_URL = os.environ.get("N8N_CAMPAIGN_WEBHOOK_URL", "")
N8N_REPLY_WEBHOOK_URL = os.environ.get("N8N_REPLY_WEBHOOK_URL", "")

# ── Instantly ─────────────────────────────────────────────────────────────────
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "")

# ── Anthropic / Claude ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "voxlead2026")

# ── App ───────────────────────────────────────────────────────────────────────
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")
PORT = int(os.environ.get("PORT", "3000"))

# ── Pricing plans ─────────────────────────────────────────────────────────────
PLANS = {
    "starter": {
        "name": "Starter",
        "price": 497,
        "leads": 500,
        "stripe_price_id": STRIPE_PRICE_STARTER,
        "features": [
            "500 verified leads",
            "AI-personalized emails",
            "AI reply agent (24/7)",
            "1 target industry",
            "Email deliverability setup",
            "Monthly campaign report",
        ],
    },
    "growth": {
        "name": "Growth",
        "price": 997,
        "leads": 2000,
        "stripe_price_id": STRIPE_PRICE_GROWTH,
        "features": [
            "2,000 verified leads",
            "AI-personalized emails",
            "AI reply agent (24/7)",
            "Up to 3 target industries",
            "A/B subject line testing",
            "Weekly performance reports",
            "Dedicated campaign manager",
        ],
    },
    "elite": {
        "name": "Elite",
        "price": 1997,
        "leads": 5000,
        "stripe_price_id": STRIPE_PRICE_ELITE,
        "features": [
            "5,000 verified leads",
            "AI-personalized emails",
            "AI reply agent (24/7)",
            "Unlimited industries",
            "Multi-step sequences",
            "Real-time dashboard access",
            "Priority support",
            "Custom sender domains",
        ],
    },
}

# ── Airtable field IDs (for reference) ────────────────────────────────────────
CLIENTS_FIELDS = {
    "company_name": "fldHmeUr4LpfDwegu",
    "contact_name": "fldwpA0etKpIkb1Qm",
    "contact_email": "fldoRDE0pjvFm7NHI",
    "what_they_sell": "fldWwkH42iWb8CXYR",
    "target_location": "fldJ2A2yflPMbB6rF",
    "lead_volume": "fldYicD7JnyZeR0zE",
    "package": "fld5i8m49GLgWwIde",
    "status": "fld0IF7zr0g8FHlfJ",
    "leads_researched": "fldXkVoyMtTpRLXub",
    "emails_sent": "fldv0j52vTIWeVpir",
    "replies_received": "fldhwcGnAgVTEonOI",
    "cost_tracked": "fldcYfby55s18ALVL",
    "n8n_campaign_id": "fld3z1Ew4VjPeDEeW",
    "notes": "fldFnwHeA9gaTnAYl",
    "submitted_at": "fldUGK9FeaK95aNa9",
}
