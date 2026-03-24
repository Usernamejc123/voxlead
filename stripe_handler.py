"""
Stripe integration for Voxlead.
Handles checkout session creation and webhook processing.
"""

import json
import hmac
import hashlib
import time
import requests
from urllib.parse import urlencode
import config
import airtable_client


def _stripe_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make an authenticated request to the Stripe API."""
    url = f"https://api.stripe.com/v1/{endpoint}"
    headers = {"Authorization": f"Bearer {config.STRIPE_SECRET_KEY}"}

    if method.upper() == "POST":
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = requests.post(url, headers=headers, data=data or {})
    else:
        resp = requests.get(url, headers=headers, params=data)

    resp.raise_for_status()
    return resp.json()


def _flatten_dict(d: dict, parent_key: str = "", sep: str = "[") -> dict:
    """Flatten nested dict for Stripe's form encoding.
    e.g. {"metadata": {"plan": "starter"}} -> {"metadata[plan]": "starter"}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}]" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep="[").items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    items.extend(
                        _flatten_dict(item, f"{new_key}[{i}]", sep="[").items()
                    )
                else:
                    items.append((f"{new_key}[{i}]", item))
        else:
            items.append((new_key, v))
    return dict(items)


def create_checkout_session(
    plan: str,
    company_name: str,
    contact_name: str,
    contact_email: str,
    what_they_sell: str,
    target_location: str,
) -> dict:
    """
    Create a Stripe Checkout Session for the given plan.
    Returns the session object with url for redirect.
    """
    plan_info = config.PLANS.get(plan.lower())
    if not plan_info:
        raise ValueError(f"Invalid plan: {plan}")

    params = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "line_items[0][price]": plan_info["stripe_price_id"],
        "line_items[0][quantity]": "1",
        "success_url": f"{config.APP_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{config.APP_URL}/signup?cancelled=true",
        "customer_email": contact_email,
        "metadata[plan]": plan.lower(),
        "metadata[company_name]": company_name,
        "metadata[contact_name]": contact_name,
        "metadata[contact_email]": contact_email,
        "metadata[what_they_sell]": what_they_sell,
        "metadata[target_location]": target_location,
        "metadata[lead_volume]": str(plan_info["leads"]),
    }

    return _stripe_request("POST", "checkout/sessions", data=params)


def verify_webhook_signature(payload: bytes, sig_header: str) -> dict:
    """
    Verify a Stripe webhook signature and return the parsed event.
    Raises ValueError if signature is invalid.
    """
    if not config.STRIPE_WEBHOOK_SECRET:
        # In development, skip verification
        return json.loads(payload)

    # Parse the signature header
    elements = dict(
        item.split("=", 1) for item in sig_header.split(",") if "=" in item
    )
    timestamp = elements.get("t", "")
    signatures = [
        v for k, v in elements.items() if k.startswith("v1")
    ]

    if not timestamp or not signatures:
        raise ValueError("Invalid signature header format")

    # Check timestamp tolerance (5 minutes)
    if abs(time.time() - int(timestamp)) > 300:
        raise ValueError("Webhook timestamp too old")

    # Compute expected signature
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
    expected_sig = hmac.new(
        config.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not any(hmac.compare_digest(expected_sig, sig) for sig in signatures):
        raise ValueError("Invalid webhook signature")

    return json.loads(payload)


def handle_checkout_completed(event: dict) -> dict:
    """
    Handle a checkout.session.completed event.
    Creates the client record in Airtable with 'paid' status.
    Returns the created Airtable record.
    """
    session = event.get("data", {}).get("object", {})
    metadata = session.get("metadata", {})

    plan = metadata.get("plan", "starter")
    plan_info = config.PLANS.get(plan, config.PLANS["starter"])

    fields = {
        "Company Name": metadata.get("company_name", ""),
        "Contact Name": metadata.get("contact_name", ""),
        "Contact Email": metadata.get("contact_email", ""),
        "What They Sell": metadata.get("what_they_sell", ""),
        "Target Location": metadata.get("target_location", ""),
        "Lead Volume": plan_info["leads"],
        "Package": plan.capitalize(),
        "Status": "paid",
        "Leads Researched": 0,
        "Emails Sent": 0,
        "Replies Received": 0,
        "Cost Tracked": 0,
        "Notes": f"Stripe session: {session.get('id', 'unknown')}",
    }

    record = airtable_client.create_client(fields)
    return record
