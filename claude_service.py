"""
Claude API — generate cold email icebreakers directly.
Requires ANTHROPIC_API_KEY environment variable.
"""
import json
import os
import urllib.error
import urllib.request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def generate_icebreaker(lead: dict) -> str:
    """
    Generate a 1-2 sentence personalized cold email opener for a lead.
    Falls back to a generic greeting if no API key is set.
    """
    first = lead.get("first_name", "there")
    company = lead.get("company", "")
    title = lead.get("title", "")
    industry = lead.get("industry", "")

    if not ANTHROPIC_API_KEY:
        return f"Hi {first},"

    prompt = (
        "Write a 1-2 sentence personalized cold email opening for this lead.\n"
        f"Name: {first} {lead.get('last_name', '')}\n"
        f"Company: {company}\n"
        f"Title: {title}\n"
        f"Industry: {industry}\n\n"
        "Rules:\n"
        "- Sound natural, not salesy\n"
        "- Reference something specific about them or their company\n"
        "- End with a comma so the rest of the email follows naturally\n"
        "- Max 2 sentences\n"
        "Output ONLY the icebreaker text, nothing else."
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 120,
        "messages": [{"role": "user", "content": prompt}],
    }

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )
    req.add_header("x-api-key", ANTHROPIC_API_KEY)
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"[Claude] icebreaker error: {e}")
        return f"Hi {first},"
