"""
Voxlead Configuration — All environment variables and constants.

Required environment variables:
  STRIPE_SECRET_KEY          - Stripe secret key (sk_test_... or sk_live_...)
  STRIPE_WEBHOOK_SECRET      - Stripe webhook signing secret (whsec_...)
  STRIPE_PRICE_STARTER       - Stripe Price ID for Starter plan
  STRIPE_PRICE_GROWTH        - Stripe Price ID for Growth plan
  STRIPE_PRICE_SCALE         - Stripe Price ID for Scale plan
  AIRTABLE_API_KEY           - Airtable personal access token (pat...)
  AIRTABLE_BASE_ID           - Airtable base ID (app...)
  MAKE_CAMPAIGN_WEBHOOK_URL  - Make.com "Voxlead — Campaign Trigger" webhook URL
  MAKE_APOLLO_WEBHOOK_URL    - Make.com "05 — Apollo Lead Sourcing" webhook URL
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
STRIPE_PRICE_SCALE = os.environ.get("STRIPE_PRICE_SCALE", "price_scale_placeholder")

# ── Airtable ─────────────────────────────────────────────────────────────────
AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "app6VovTdNZtSbOli")
AIRTABLE_CLIENTS_TABLE = "tbliRFtZV1Kfzb7ZK"
AIRTABLE_LEADS_TABLE = "tblXKBbXFNyuwUAyq"

# ── Make.com ──────────────────────────────────────────────────────────────────
MAKE_CAMPAIGN_WEBHOOK_URL = os.environ.get(
    "MAKE_CAMPAIGN_WEBHOOK_URL",
    "https://hook.us2.make.com/4egm5dyqdbu1p54l1r46cv4fc8v962kd",
)
MAKE_APOLLO_WEBHOOK_URL = os.environ.get(
    "MAKE_APOLLO_WEBHOOK_URL",
    "https://hook.us2.make.com/9ir5aamaf6a2x36ncxsxzvh9ul3nuqjp",
)

# ── Dashboard ─────────────────────────────────────────────────────────────────
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "voxlead2026")

# ── App ───────────────────────────────────────────────────────────────────────
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")
PORT = int(os.environ.get("PORT", "3000"))

# ── Pricing plans (for display and validation) ────────────────────────────────
PLANS = {
    "starter": {
        "name": "Starter",
        "price": 497,
        "leads": 500,
        "stripe_price_id": STRIPE_PRICE_STARTER,
        "features": [
            "500 verified leads",
            "AI-personalized emails",
            "1 target industry",
            "Email deliverability setup",
            "Campaign report",
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
            "Up to 3 target industries",
            "A/B subject line testing",
            "Weekly performance reports",
            "Dedicated campaign manager",
        ],
    },
    "scale": {
        "name": "Scale",
        "price": 1997,
        "leads": 5000,
        "stripe_price_id": STRIPE_PRICE_SCALE,
        "features": [
            "5,000 verified leads",
            "AI-personalized emails",
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
    "make_campaign_id": "fld3z1Ew4VjPeDEeW",
    "notes": "fldFnwHeA9gaTnAYl",
    "submitted_at": "fldUGK9FeaK95aNa9",
}
