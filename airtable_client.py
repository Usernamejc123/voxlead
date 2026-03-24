"""
Airtable API client for Voxlead.
Handles all reads/writes to the Clients and Leads tables.
"""

import json
import requests
from typing import Optional
import config


def _headers():
    return {
        "Authorization": f"Bearer {config.AIRTABLE_API_KEY}",
        "Content-Type": "application/json",
    }


def _base_url(table_id: str) -> str:
    return f"https://api.airtable.com/v0/{config.AIRTABLE_BASE_ID}/{table_id}"


# ── Clients ───────────────────────────────────────────────────────────────────


def list_clients(
    status_filter: Optional[str] = None, max_records: int = 100
) -> list[dict]:
    """Fetch all client records, optionally filtered by status."""
    params: dict = {"maxRecords": str(max_records)}
    if status_filter:
        params["filterByFormula"] = f'{{Status}}="{status_filter}"'

    resp = requests.get(
        _base_url(config.AIRTABLE_CLIENTS_TABLE),
        headers=_headers(),
        params=params,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("records", [])


def get_client(record_id: str) -> dict:
    """Fetch a single client record by ID."""
    resp = requests.get(
        f"{_base_url(config.AIRTABLE_CLIENTS_TABLE)}/{record_id}",
        headers=_headers(),
    )
    resp.raise_for_status()
    return resp.json()


def create_client(fields: dict) -> dict:
    """Create a new client record. Returns the created record."""
    payload = {"records": [{"fields": fields}]}
    resp = requests.post(
        _base_url(config.AIRTABLE_CLIENTS_TABLE),
        headers=_headers(),
        json=payload,
    )
    resp.raise_for_status()
    records = resp.json().get("records", [])
    return records[0] if records else {}


def update_client(record_id: str, fields: dict) -> dict:
    """Update a client record. Returns the updated record."""
    payload = {"fields": fields}
    resp = requests.patch(
        f"{_base_url(config.AIRTABLE_CLIENTS_TABLE)}/{record_id}",
        headers=_headers(),
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


# ── Leads ─────────────────────────────────────────────────────────────────────


def list_leads(
    status_filter: Optional[str] = None, max_records: int = 100
) -> list[dict]:
    """Fetch lead records, optionally filtered by pipeline status."""
    params: dict = {"maxRecords": str(max_records)}
    if status_filter:
        params["filterByFormula"] = f'{{{" Pipeline Status"}}}="{status_filter}"'

    resp = requests.get(
        _base_url(config.AIRTABLE_LEADS_TABLE),
        headers=_headers(),
        params=params,
    )
    resp.raise_for_status()
    return resp.json().get("records", [])


def count_leads_by_status() -> dict:
    """Get counts of leads grouped by Pipeline Status."""
    all_leads = list_leads(max_records=1000)
    counts: dict = {}
    for lead in all_leads:
        status = lead.get("fields", {}).get("Pipeline Status", "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


# ── Dashboard Stats ───────────────────────────────────────────────────────────


def get_dashboard_stats() -> dict:
    """
    Aggregate all stats for the operator dashboard:
    - Total clients, by status
    - Total leads, by pipeline status
    - Emails sent, replies received (summed from clients)
    - Cost per lead estimate
    """
    clients = list_clients(max_records=500)
    lead_counts = count_leads_by_status()

    total_clients = len(clients)
    total_leads_researched = 0
    total_emails_sent = 0
    total_replies = 0
    total_cost = 0.0
    total_revenue = 0.0

    status_counts = {}
    client_summaries = []

    for rec in clients:
        f = rec.get("fields", {})
        status = f.get("Status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

        leads_r = f.get("Leads Researched") or 0
        emails_s = f.get("Emails Sent") or 0
        replies_r = f.get("Replies Received") or 0
        cost = f.get("Cost Tracked") or 0.0
        package = f.get("Package", "starter")

        total_leads_researched += leads_r
        total_emails_sent += emails_s
        total_replies += replies_r
        total_cost += cost

        plan_info = config.PLANS.get(
            (package or "starter").lower(),
            config.PLANS["starter"],
        )
        total_revenue += plan_info["price"]

        client_summaries.append(
            {
                "id": rec["id"],
                "company_name": f.get("Company Name", ""),
                "contact_name": f.get("Contact Name", ""),
                "contact_email": f.get("Contact Email", ""),
                "what_they_sell": f.get("What They Sell", ""),
                "target_location": f.get("Target Location", ""),
                "lead_volume": f.get("Lead Volume", 0),
                "package": package,
                "status": status,
                "leads_researched": leads_r,
                "emails_sent": emails_s,
                "replies_received": replies_r,
                "cost_tracked": cost,
                "make_campaign_id": f.get("Make Campaign ID", ""),
                "notes": f.get("Notes", ""),
                "submitted_at": f.get("Submitted At", ""),
            }
        )

    cost_per_lead = (
        round(total_cost / total_leads_researched, 4)
        if total_leads_researched > 0
        else 0.025
    )

    return {
        "total_clients": total_clients,
        "client_status_counts": status_counts,
        "total_leads_researched": total_leads_researched,
        "total_emails_sent": total_emails_sent,
        "total_replies": total_replies,
        "total_cost": round(total_cost, 2),
        "total_revenue": total_revenue,
        "cost_per_lead": cost_per_lead,
        "reply_rate": (
            round((total_replies / total_emails_sent) * 100, 1)
            if total_emails_sent > 0
            else 0
        ),
        "lead_pipeline": lead_counts,
        "clients": client_summaries,
    }
