"""
Instantly.ai webhook handler and AI Sales Agent for Voxlead.

Processes Instantly webhook events:
  - reply_received      : real human replied to a sequence email
  - auto_reply_received : OOO / bot auto-response

For each genuine reply the handler:
  1. Classifies the intent with Claude AI
  2. Updates the matching client record in Airtable (Replies Received++)
  3. If the lead is "interested", fires the n8n hot-lead reply webhook
     so the client gets notified and a calendar link is sent back automatically.

Instantly webhook payload (reply_received example):
{
  "event_type": "reply_received",
  "timestamp": "2026-03-29T12:00:00Z",
  "campaign_id": "abc123",
  "campaign_name": "Q1 Tech Outreach",
  "lead": {
    "email": "john@acme.com",
    "first_name": "John",
    "last_name": "Smith",
    "company_name": "Acme Corp"
  },
  "reply": {
    "subject": "Re: Quick question",
    "body": "Yes, this sounds interesting. Can we jump on a call?",
    "from_email": "john@acme.com",
    "timestamp": "2026-03-29T12:00:00Z"
  }
}
"""

import json
import os
import requests
import config

# ── Anthropic / Claude ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# ── Instantly API v2 ──────────────────────────────────────────────────────────
INSTANTLY_API_KEY = os.environ.get("INSTANTLY_API_KEY", "")
INSTANTLY_API_URL = "https://api.instantly.ai/api/v2"

# ── Intent labels ─────────────────────────────────────────────────────────────
INTENT_INTERESTED = "interested"
INTENT_NOT_INTERESTED = "not_interested"
INTENT_OOO = "out_of_office"
INTENT_MORE_INFO = "more_info_needed"
INTENT_UNKNOWN = "unknown"


def _classify_reply(reply_body: str, lead_info: dict) -> dict:
    """
    Call Claude Haiku to classify the reply intent and draft a follow-up.
    Returns: {"intent": str, "summary": str, "suggested_reply": str}
    Falls back gracefully if Anthropic key is not set.
    """
    if not ANTHROPIC_API_KEY:
        return {
            "intent": INTENT_UNKNOWN,
            "summary": "No Anthropic API key configured — manual review needed.",
            "suggested_reply": "",
        }

    first_name = lead_info.get("first_name", "there")
    company = lead_info.get("company_name", "your company")

    system_prompt = """You are an expert sales reply classifier for a cold email agency.
Your job is to read a prospect's email reply and output a JSON object with:
- intent: one of "interested", "not_interested", "out_of_office", "more_info_needed"
- summary: one sentence describing what the prospect said
- suggested_reply: a natural, brief reply the sender should send back (2-3 sentences max). Leave empty string if not_interested or out_of_office.

Be concise. Output ONLY valid JSON with no extra text."""

    user_prompt = f"""Prospect: {first_name} at {company}
Reply body:
---
{reply_body[:2000]}
---
Classify this reply."""

    try:
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 300,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=20,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"].strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {
            "intent": INTENT_UNKNOWN,
            "summary": f"Classification failed: {str(e)[:100]}",
            "suggested_reply": "",
        }


def _find_client_by_campaign(campaign_id: str) -> dict | None:
    """
    Look up the Airtable client record that matches the given Instantly campaign ID.
    Searches the 'Make Campaign ID' field.
    Returns the record dict or None.
    """
    try:
        import airtable_client
        clients = airtable_client.list_clients(max_records=200)
        for rec in clients:
            fields = rec.get("fields", {})
            if fields.get("Make Campaign ID") == campaign_id:
                return rec
    except Exception:
        pass
    return None


def _increment_airtable_replies(client_record_id: str, notes_append: str = "") -> bool:
    """
    Increment Replies Received counter in Airtable for the matching client.
    Optionally append to the Notes field.
    """
    try:
        import airtable_client
        client = airtable_client.get_client(client_record_id)
        current_replies = client.get("fields", {}).get("Replies Received", 0) or 0
        current_notes = client.get("fields", {}).get("Notes", "") or ""

        update_fields = {"Replies Received": current_replies + 1}
        if notes_append:
            update_fields["Notes"] = (
                current_notes + ("\n\n" if current_notes else "") + notes_append
            )

        airtable_client.update_client(client_record_id, update_fields)
        return True
    except Exception:
        return False


def _notify_hot_lead(campaign_id: str, lead: dict, classification: dict) -> bool:
    """
    Fire the n8n hot-lead webhook when a prospect is classified as interested.
    n8n handles:
      - Sending the prospect a calendar booking link
      - Notifying the operator via Slack/email
      - Logging the hot lead in Airtable
    """
    import n8n_handler
    payload = {
        "event": "hot_lead",
        "campaign_id": campaign_id,
        "lead_email": lead.get("email", ""),
        "lead_name": f"{lead.get('first_name', '')} {lead.get('last_name', '')}".strip(),
        "lead_company": lead.get("company_name", ""),
        "intent": classification.get("intent", ""),
        "summary": classification.get("summary", ""),
        "suggested_reply": classification.get("suggested_reply", ""),
    }
    result = n8n_handler.trigger_hot_lead_reply(payload)
    return result.get("success", False)


def handle_reply_received(event: dict) -> dict:
    """
    Main handler for Instantly reply_received and auto_reply_received webhooks.

    Flow:
      1. Extract lead + reply data from event payload
      2. Skip auto-replies (OOO) early unless they need special handling
      3. Classify intent with Claude AI
      4. Update Airtable reply counter
      5. If interested → fire hot-lead Make.com webhook
      6. Return result summary
    """
    event_type = event.get("event_type", "reply_received")
    campaign_id = event.get("campaign_id", "")
    campaign_name = event.get("campaign_name", "")
    lead = event.get("lead", {})
    reply = event.get("reply", {})
    reply_body = reply.get("body", "")

    result = {
        "event_type": event_type,
        "campaign_id": campaign_id,
        "lead_email": lead.get("email", ""),
        "intent": INTENT_UNKNOWN,
        "summary": "",
        "suggested_reply": "",
        "airtable_updated": False,
        "hot_lead_notified": False,
    }

    # Auto-replies (OOO) — classify but don't fire hot-lead webhook
    is_auto = event_type == "auto_reply_received"

    # Classify intent
    classification = _classify_reply(reply_body, lead)
    intent = classification.get("intent", INTENT_UNKNOWN)
    result["intent"] = intent
    result["summary"] = classification.get("summary", "")
    result["suggested_reply"] = classification.get("suggested_reply", "")

    # Find matching Airtable client record
    client_rec = _find_client_by_campaign(campaign_id)

    if client_rec:
        notes_line = (
            f"[{event_type}] {lead.get('email', '')} — {campaign_name}: {result['summary']}"
        )
        updated = _increment_airtable_replies(client_rec["id"], notes_append=notes_line)
        result["airtable_updated"] = updated
        result["client_record_id"] = client_rec["id"]

    # Fire hot-lead webhook for genuinely interested replies
    if intent == INTENT_INTERESTED and not is_auto:
        notified = _notify_hot_lead(campaign_id, lead, classification)
        result["hot_lead_notified"] = notified

    return result


def get_campaign_analytics(campaign_id: str) -> dict:
    """
    Fetch live analytics for an Instantly campaign via API v2.
    Returns opens, clicks, replies, leads contacted.
    """
    if not INSTANTLY_API_KEY:
        return {"error": "INSTANTLY_API_KEY not configured"}

    try:
        resp = requests.get(
            f"{INSTANTLY_API_URL}/campaigns/{campaign_id}/analytics",
            headers={
                "Authorization": f"Bearer {INSTANTLY_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)[:200]}


def list_campaigns() -> list:
    """
    List all Instantly campaigns via API v2.
    """
    if not INSTANTLY_API_KEY:
        return []

    try:
        resp = requests.get(
            f"{INSTANTLY_API_URL}/campaigns",
            headers={
                "Authorization": f"Bearer {INSTANTLY_API_KEY}",
                "Content-Type": "application/json",
            },
            params={"limit": 100},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("items", data) if isinstance(data, dict) else data
    except Exception:
        return []
