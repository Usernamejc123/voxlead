"""
Voxlead Make.com / n8n Handler
Triggers automation workflows when operator launches a campaign.
Defaults to Make.com webhook — override with N8N_CAMPAIGN_WEBHOOK_URL env var.

Flow:
  Operator clicks "Launch Campaign" in dashboard
  → server.py calls trigger_campaign(record_id)
  → POSTs to Make.com "Voxlead — Campaign Trigger" webhook
  → Make.com: updates Airtable status → Apollo sourcing → NeverBounce → Claude → Instantly
"""

import json
import urllib.request
import urllib.error
import traceback

import config
import airtable_client


# Make.com webhook URLs (used when env vars not set)
_MAKE_CAMPAIGN_URL = "https://hook.us2.make.com/4egm5dyqdbu1p54l1r46cv4fc8v962kd"
_MAKE_HOT_LEAD_URL = "https://hook.us2.make.com/4egm5dyqdbu1p54l1r46cv4fc8v962kd"


# ── Trigger: Launch Campaign ──────────────────────────────────────────────────

def trigger_campaign(record_id: str) -> dict:
    """
    Trigger the campaign pipeline for a client.
    Called when operator clicks 'Launch Campaign' in the dashboard.
    Sends to Make.com 'Voxlead — Campaign Trigger' webhook by default.
    """
    webhook_url = getattr(config, 'N8N_CAMPAIGN_WEBHOOK_URL', None) or _MAKE_CAMPAIGN_URL

    # Fetch client record from Airtable to build payload
    try:
        record = airtable_client.get_client(record_id)
        fields = record.get('fields', {}) if record else {}
    except Exception:
        fields = {}

    payload = {
        "client_id":       record_id,
        "company_name":    fields.get('Company Name') or fields.get('company_name', ''),
        "what_they_sell":  fields.get('What They Sell') or fields.get('what_they_sell', ''),
        "target_location": fields.get('Target Location') or fields.get('target_location', 'United States'),
        "target_industry": fields.get('Target Industry') or fields.get('target_industry', ''),
        "target_titles":   fields.get('Target Titles') or fields.get('target_titles', 'CEO,Founder,VP Sales'),
        "company_size":    fields.get('Company Size') or fields.get('company_size', '11-50,51-200'),
        "plan":            fields.get('Package') or fields.get('package', 'starter'),
        "lead_volume":     _get_lead_volume(fields.get('Package') or fields.get('package', 'starter')),
        "contact_email":   fields.get('Contact Email') or fields.get('contact_email', ''),
        "contact_name":    fields.get('Contact Name') or fields.get('contact_name', ''),
    }

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            try:
                result = json.loads(body)
            except Exception:
                result = {"raw": body}
            return {"triggered": True, "webhook": webhook_url, "result": result}
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"[n8n_handler] Campaign trigger HTTP {e.code}: {body}")
        return {"triggered": False, "error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        print(f"[n8n_handler] Campaign trigger error: {e}")
        traceback.print_exc()
        return {"triggered": False, "error": str(e)}


# ── Trigger: Hot Lead Reply ───────────────────────────────────────────────────

def trigger_hot_lead_reply(lead_data: dict) -> dict:
    """
    Notify Make.com / n8n of a hot lead (interested reply from Instantly).
    Called by instantly_handler when AI classifies a reply as 'interested'.
    """
    webhook_url = getattr(config, 'N8N_REPLY_WEBHOOK_URL', None) or _MAKE_HOT_LEAD_URL

    if not webhook_url:
        print("[n8n_handler] No reply webhook URL configured, skipping hot lead notification")
        return {"triggered": False, "reason": "no_webhook_url"}

    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(lead_data).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            try:
                result = json.loads(body)
            except Exception:
                result = {"raw": body}
            return {"triggered": True, "result": result}
    except Exception as e:
        print(f"[n8n_handler] Hot lead trigger error: {e}")
        return {"triggered": False, "error": str(e)}


# ── Handle Status Callback ────────────────────────────────────────────────────

def handle_status_callback(data: dict) -> dict:
    """
    Handle a status update callback from Make.com / n8n.
    Updates Airtable client record with campaign progress.
    """
    record_id = data.get('client_id') or data.get('record_id', '')
    status    = data.get('status', '')
    updates   = {}

    if status:
        updates['Status'] = _map_status(status)
    if data.get('emails_sent') is not None:
        updates['Emails Sent'] = int(data['emails_sent'])
    if data.get('leads_sourced') is not None:
        updates['Leads Researched'] = int(data['leads_sourced'])
    if data.get('instantly_campaign_id'):
        updates['Instantly Campaign ID'] = data['instantly_campaign_id']
    if data.get('notes'):
        updates['Notes'] = data['notes']

    if record_id and updates:
        try:
            airtable_client.update_client(record_id, updates)
        except Exception as e:
            print(f"[n8n_handler] Airtable update error: {e}")
            return {"ok": False, "error": str(e)}

    return {"ok": True, "record_id": record_id, "updated": list(updates.keys())}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_lead_volume(plan: str) -> int:
    plan = (plan or '').lower()
    if 'elite' in plan:
        return 5000
    if 'growth' in plan:
        return 2000
    return 500  # starter default


def _map_status(status: str) -> str:
    mapping = {
        'running':           'campaign_active',
        'campaign_active':   'campaign_active',
        'active':            'campaign_active',
        'paused':            'paused',
        'complete':          'complete',
        'completed':         'complete',
        'error':             'pending_review',
        'failed':            'pending_review',
    }
    return mapping.get(status.lower(), status)
