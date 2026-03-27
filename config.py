"""
Voxlead Configuration
"""
import os

# ── Instantly ──────────────────────────────────────────────────────────────
INSTANTLY_API_KEY = os.environ.get(
    "INSTANTLY_API_KEY",
    "NTY4OVU3OTktMmY1NC00MDI5LTk0YzktOWZlMmZmOGZmY2JmOnZXV0pCUlJvYWlDRg=="
)

# ── Claude / Anthropic ───────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Dashboard ─────────────────────────────────────────────────────────────
DASHBOARD_PASSWORD = os.environ.get("DASHCOARD_PASSWORD", "voxlead2026")

# ── App ──────────────────────────────────────────────────────────────────
APP_URL = os.environ.get("APP_URL", "http://localhost:8080")
PORT = int(os.environ.get("PORT", "8080"))
