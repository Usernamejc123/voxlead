"""
Make.com integration for Voxlead.
Triggers campaign automation and handles status callbacks.
"""

import json
import requests
import config
import airtable_client


def trigger_campaign(client_record_id: str) -> dict:
    """
    Trigger a campaign for a client by:
    1. Updating client status to 'running' in Airtable
    2. Sending webhook to Make.com "Voxlead — Campaign Trigger"

    The Make.com scenario will then:
    - Call Apollo Lead Sourcing to find prospects
    - Pipeline flows through validation → enrichment → Instantly

    Returns the Make.com webhook response.
    """
    # Fetch the client record
    client = airtable_client.get_client(client_record_id)
    fields = client.get("fields", {})

    # Update status to running
    airtable_client.update_client(client_record_id, {"Status": "running"})

    # Build the payload for Make.com
    plan = (fields.get("Package") or "starter").lower()
    payload = {
        "client_id": client_record_id,
        "company_name": fields.get("Company Name", ""),
        "contact_name": fields.get("Contact Name", ""),
        "contact_email": fields.get("Contact Email", ""),
        "what_they_sell": fields.get("What They Sell", ""),
        "target_location": fields.get("Target Location", ""),
        "lead_volume": fields.get("Lead Volume", 500),
        "plan": plan,
        "status_callback_url": f"{config.APP_URL}/api/webhooks/status",
    }

    # Fire the webhook
    resp = requests.post(
        config.MAKE_CAMPAIGN_WEBHOOK_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=30,
    )

    return {
        "success": resp.status_code in (200, 201, 202),
        "status_code": resp.status_code,
        "response": resp.text[:500],
        "client_id": client_record_id,
    }


def handle_status_callback(data: dict) -> dict:
    """
    Handle a status callback from Make.com.
    Updates the client record in Airtable with campaign progress.

    Expected payload:
    {
        "client_id": "recXXXX",
        "leads_researched": 150,
        "emails_sent": 120,
        "replies_received": 8,
        "cost_tracked": 3.75,
        "status": "running" | "completed" | "paused" | "failed",
        "notes": "optional progress note"
    }
    """
    client_id = data.get("client_id")
    if not client_id:
        return {"error": "Missing client_id"}

    update_fields = {}

    if "leads_researched" in data:
        update_fields["Leads Researched"] = int(data["leads_researched"])
    if "emails_sent" in data:
        update_fields["Emails Sent"] = int(data["emails_sent"])
    if "replies_received" in data:
        update_fields["Replies Received"] = int(data["replies_received"])
    if "cost_tracked" in data:
        update_fields["Cost Tracked"] = float(data["cost_tracked"])
    if "status" in data:
        update_fields["Status"] = data["status"]
    if "notes" in data:
        update_fields["Notes"] = data["notes"]
    if "make_campaign_id" in data:
        update_fields["Make Campaign ID"] = data["make_campaign_id"]

    if update_fields:
        airtable_client.update_client(client_id, update_fields)

    return {"success": True, "updated_fields": list(update_fields.keys())}
