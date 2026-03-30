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
  N8N_CAMPAIBN_WEBHOOK_URL   - n8n webhook URL to trigger campaign pipeline
  N8N_REPLY_WEBHOOK_URL      - n8n webhook URL for hot-lead reply handling
  INSTANTLY_API_KEY          - Instantly.ai API v2 key
  ANTHROPIC_API_KEY          - Claude AI key (for personalization + reply classification)
  DASHBOARD_PASSWORD         - Password to access operator dashboard
  APP_URL                    - Public URL of the app (https://yourdomain.com)
  PORT                       - Server port (default 3000)
"""

import os

# ── Stripe ─────────────────────────────────────────────────────────────────
APP_URL = os.environ.get("APP_URL", "http://localhost:3000")
PORT = int(os.environ.get("PORT", "3000"))
