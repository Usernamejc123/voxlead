"""
Instantly v2 API — simple wrapper using only stdlib.
"""
import base64
import gzip
import json
import os
import urllib.error
import urllib.request

# Primary key (workspace:secret format, base64 stored)
_KEY_PRIMARY  = "NTY4OWU3OTktM2Y1NC00MDI5LTk0YzktOWZlM2FmOGZmY2JmOktPSXJhb1lEWlRMSw=="
# Fallback key
_KEY_FALLBACK = "NTY4OWU3OTktM2Y1NC00MDI5LTk0YzktOWZlM2FmOGZmY2ImOnZWV0pCUlJvYWlDRg=="

INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", _KEY_PRIMARY)
BASE = "https://api.instantly.ai/api/v2"


def _decode_key(k):
    try:
        decoded = base64.b64decode(k).decode("utf-8")
        if ":" in decoded or "-" in decoded:
            return decoded
    except Exception:
        pass
    return k


def _get_key():
    return _decode_key(INSTANTLY_API_KEY)


def _decompress(raw):
    """Try gzip decompress, return as-is if not compressed."""
    try:
        return gzip.decompress(raw)
    except Exception:
        return raw


_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


def _req(method, path, data=None, api_key=None):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method=method)
    for k, v in _HEADERS.items():
        req.add_header(k, v)
    key = api_key or _get_key()
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = _decompress(resp.read())
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = _decompress(e.read())
        raw_str = raw.decode("utf-8", errors="replace")
        try:
            return {"_error": True, "status_code": e.code, "detail": json.loads(raw_str)}
        except Exception:
            return {"_error": True, "status_code": e.code, "detail": raw_str[:500]}
    except Exception as exc:
        return {"_error": True, "status_code": 0, "detail": str(exc)}


def _req_with_fallback(method, path, data=None):
    """Try primary key, auto-fallback to secondary on 401/403."""
    result = _req(method, path, data)
    if result.get("_error") and result.get("status_code") in (401, 403):
        fallback = _decode_key(_KEY_FALLBACK)
        result2 = _req(method, path, data, api_key=fallback)
        if not result2.get("_error"):
            return result2
    return result


# ── Public helpers ────────────────────────────────────────────────────────────

def list_campaigns(limit=100, skip=0):
    return _req_with_fallback("GET", f"/campaigns?limit={limit}&skip={skip}")


def get_campaign(campaign_id: str):
    return _req_with_fallback("GET", f"/campaigns/{campaign_id}")


def create_campaign(name: str):
    return _req_with_fallback("POST", "/campaigns", {"name": name})


def get_analytics(campaign_id: str):
    return _req_with_fallback("GET", f"/analytics/campaigns/summary?id={campaign_id}&start=2024-01-01&end=2099-01-01")


def upload_leads(campaign_id: str, leads: list):
    return _req_with_fallback("POST", "/leads", {
        "campaign_id": campaign_id,
        "leads": leads,
        "skip_if_in_workspace": True,
    })


def set_campaign_status(campaign_id: str, status: int):
    # status: 1 = active, 2 = paused
    return _req_with_fallback("PATCH", f"/campaigns/{campaign_id}", {"status": status})
