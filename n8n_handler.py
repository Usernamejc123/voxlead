"""
Voxlead n8n Handler
Replaces Make.com — triggers n8n workflows and handles callbacks.

n8n Workflow Architecture:
  Workflow 01 — Client Intake → Campaign Launch
    Trigger: POST /api/webhooks/n8n/launch
    Steps: Airtable fetch → Apollo lead pull → NeverBounce validate → Claude personalize → Instantly push

  Workflow 02 — Hot Lead Reply
    Trigger: POST /api/webhooks/n8n/reply
    Steps: Classify reply → If interested → Send Calendly link → Notify operator via Slack

  Webhook back to VoxLead:
    n8n calls POST /api/webhooks/status when campaign progress updates
"""

import json
import urllib.request
import urllib.error
import traceback

import config
import airtable_client


# ── Trigger: Launch Campaign ──────────────────────────────────────────────────

def trigger_campaign(record_id: str) -> dict:
    """
    Trigger the n8n campaign pipeline for a client.
    Called when operator clicks 'Launch Campaign' in the dashboard.
    """
    if not config.N8N_CAMPAIGN_WEBHOOK_URL:
        # n8n not configured yet — update status in Airtable and return
        airtable_client.update_client_status(record_id, "campaign_active")
        return {
            "success": True,
            "triggered": False,
            "message": "N8N_CAMPAIGN_WEBHOOK_URL not configured. Status updated to active.",
            "record_id": record_id,
        }

    # Fetch client record from Airtable
    client = airtable_client.get_client(record_id)
    if not client:
        return {"success": False, "error": "Client record not found"}

    fields = client.get("fields", {})

    # Build payload for n8n
    payload = {
        "record_id": record_id,
        "company_name": fields.get("Company Name", ""),
        "contact_email": fields.get("Contact Email", ""),
        "contact_name": fields.get("Contact Name", ""),
        "what_they_sell": fields.get("What They Sell", ""),
        "target_industry": fields.get("Target Industry", ""),
        "target_titles": fields.get("Target Titles", ""),
        "target_location": fields.get("Target Location", ""),
        "company_size": fields.get("Company Size", ""),
        "problem_solved": fields.get("Problem Solved", ""),
        "unique_value": fields.get("Unique Value", ""),
        "cta_type": fields.get("CTA Type", "book_call"),
        "calendly_link": fields.get("Calendly Link", ""),
        "package": fields.get("Package", "starter"),
        "lead_volume": _get_lead_volume(fields.get("Package", "starter")),
        "exclusions": fields.get("Exclusions", ""),
        "additional_notes": fields.get("Additional Notes", ""),
        "voxlead_callback_url": f"{config.APP_URL}/api/webhooks/status",
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            config.N8N_CAMPAIGN_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            try:
                result = json.loads(body)
            except Exception:
                result = {"raw": body}

        # Update Airtable status
        airtable_client.update_client_status(record_id, "campaign_active")

        return {
            "success": True,
            "triggered": True,
            "record_id": record_id,
            "n8n_response": result,
        }

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"success": False, "error": f"n8n HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ── Trigger: Hot Lead Reply ───────────────────────────────────────────────────

def trigger_hot_lead_reply(lead_data: dict) -> dict:
    """
    Fires when Instantly's AI classifies a reply as 'interested'.
    Sends lead details to n8n for follow-up automation.
    """
    if not config.N8N_REPLY_WEBHOOK_URL:
        print("[n8n] N8N_REPLY_WEBHOOK_URL not set — skipping hot lead notification")
        return {"success": False, "reason": "N8N_REPLY_WEBHOOK_URL not configured"}

    try:
        data = json.dumps(lead_data).encode("utf-8")
        req = urllib.request.Request(
            config.N8N_REPLY_WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"success": True, "n8n_response": body[:500]}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


# ── Handle: Status Callback from n8n ─────────────────────────────────────────

def handle_status_callback(data: dict) -> dict:
    """
    n8n calls this endpoint to update campaign progress in Airtable.

    Expected payload:
      {
        "record_id": "recXXX",
        "event": "leads_sourced" | "emails_sent" | "campaign_complete",
        "leads_count": 500,
        "emails_sent": 250,
        "replies": 15,
        "notes": "optional notes"
      }
    """
    record_id = data.get("record_id", "")
    event = data.get("event", "")

    if not record_id:
        return {"success": False, "error": "record_id required"}

    updates = {}

    if event == "leads_sourced":
        updates["leads_researched"] = data.get("leads_count", 0)

    elif event == "emails_sent":
        updates["emails_sent"] = data.get("emails_sent", 0)
        if data.get("status"):
            updates["status"] = data["status"]

    elif event == "reply_received":
        # Handled separately by instantly_handler, but n8n can also call this
        count = data.get("reply_count", 0)
        airtable_client.increment_replies(record_id, count)
        return {"success": True, "event": event}

    elif event == "campaign_complete":
        updates["status"] = "complete"
        if data.get("emails_sent"):
            updates["emails_sent"] = data["emails_sent"]

    elif event == "campaign_paused":
        updates["status"] = "paused"

    elif event == "error":
        updates["notes"] = f"[n8n ERROR] {data.get('error', 'Unknown error')}"

    if updates:
        try:
            airtable_client.update_client_fields(record_id, updates)
        except Exception as e:
            return {"success": False, "error": str(e)}

    return {"success": True, "event": event, "record_id": record_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_lead_volume(plan: str) -> int:
    plan_map = {"starter": 500, "growth": 2000, "elite": 5000}
    return plan_map.get(plan.lower(), 500)
