"""
Instantly v2 API — simple wrapper using only stdlib.
"""
import json
import os
import urllib.error
import urllib.request

INSTANTLY_API_KEY = os.environ.get(
    "INSTANTLY_API_KEY",
    "NTY4OWU3OTktM2Y1NC00MDI5LTk0YzktOWZlM2FmOGZmY2ImOnZWV0pCUlJvYWlDRg=="
)
BASE = "https://api.instantly.ai/api/v2"


def _req(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {INSTANTLY_API_KEY}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        try:
            return {"_error": True, "status_code": e.code, "detail": json.loads(raw)}
        except Exception:
            return {"_error": True, "status_code": e.code, "detail": raw}
    except Exception as ex:
        return {"_error": True, "detail": str(ex)}


# ── Campaigns ──────────────────────────────────────────────────────────────

def list_campaigns(limit=50):
    return _req("GET", f"/campaigns?limit={limit}")


def get_campaign(campaign_id):
    return _req("GET", f"/campaigns/{campaign_id}")


def create_campaign(name):
    return _req("POST", "/campaigns", {"name": name})


def launch_campaign(campaign_id):
    return _req("POST", f"/campaigns/{campaign_id}/activate", {})


def pause_campaign(campaign_id):
    return _req("POST", f"/campaigns/{campaign_id}/pause", {})


def get_analytics(campaign_id):
    return _req("GET", f"/campaigns/{campaign_id}/analytics/overview")


# ── Leads ─────────────────────────────────────────────────────────────────

def add_leads(campaign_id, leads):
    """
    leads: list of dicts, each with keys:
      email, first_name, last_name, company, personalization (icebreaker)
    """
    return _req("POST", "/leads", {"campaign_id": campaign_id, "leads": leads})
