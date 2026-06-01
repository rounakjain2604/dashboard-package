"""Payment-provider preparation stubs.

Live LemonSqueezy webhooks are intentionally deferred. This module only
implements a deterministic local event processor so tests can verify
idempotent crediting before real provider infrastructure is connected.
"""
from __future__ import annotations

from threading import Lock

from src.dcf_engine.saas.usage import grant_export_credits


_LOCK = Lock()
_EVENT_IDS: set[str] = set()


def process_local_payment_event(event: dict) -> dict:
    provider_event_id = str(event.get("provider_event_id") or event.get("id") or "").strip()
    email = str(event.get("email") or "").strip().lower()
    credits = int(event.get("credits", 0))
    if not provider_event_id:
        raise ValueError("provider_event_id is required")
    if not email:
        raise ValueError("email is required")
    if credits <= 0:
        raise ValueError("credits must be positive")

    with _LOCK:
        if provider_event_id in _EVENT_IDS:
            return {"processed": False, "duplicate": True}
        _EVENT_IDS.add(provider_event_id)

    balance = grant_export_credits(email, credits)
    return {"processed": True, "duplicate": False, "email": email, "credits_remaining": balance}


def reset_payment_state():
    with _LOCK:
        _EVENT_IDS.clear()
