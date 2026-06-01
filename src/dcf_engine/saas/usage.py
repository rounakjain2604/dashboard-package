"""Server-side usage and export credit rules for validation-stage gating."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class ExportAccess:
    allowed: bool
    email: str | None = None
    reason: str = ""
    checkout_url: str = ""
    consume_credit: bool = False


_LOCK = Lock()
_EXPORT_CREDITS: dict[str, int] = {}
_EXPORT_LOGS: list[dict] = []


def reset_usage_state():
    with _LOCK:
        _EXPORT_CREDITS.clear()
        _EXPORT_LOGS.clear()


def grant_export_credits(email: str, credits: int) -> int:
    clean_email = str(email or "").strip().lower()
    if not clean_email:
        raise ValueError("email is required")
    if credits <= 0:
        raise ValueError("credits must be positive")
    with _LOCK:
        _EXPORT_CREDITS[clean_email] = _EXPORT_CREDITS.get(clean_email, 0) + int(credits)
        return _EXPORT_CREDITS[clean_email]


def check_export_access(user: dict, checkout_url: str = "") -> ExportAccess:
    email = user.get("email")
    if user.get("token_valid"):
        return ExportAccess(True, email=email, reason="local export token", checkout_url=checkout_url)
    if not email:
        return ExportAccess(False, reason="anonymous users cannot export premium Excel", checkout_url=checkout_url)
    with _LOCK:
        credits = _EXPORT_CREDITS.get(email, 0)
    if credits > 0:
        return ExportAccess(True, email=email, reason="export credit available", checkout_url=checkout_url, consume_credit=True)
    return ExportAccess(False, email=email, reason="no export credits", checkout_url=checkout_url)


def consume_export_credit(email: str | None, ticker: str, warnings: list | None = None) -> None:
    if not email:
        return
    with _LOCK:
        if _EXPORT_CREDITS.get(email, 0) <= 0:
            raise PermissionError("No export credits remaining")
        _EXPORT_CREDITS[email] -= 1
        _EXPORT_LOGS.append({
            "email": email,
            "ticker": ticker,
            "status": "exported",
            "warnings": warnings or [],
        })


def export_credits(email: str) -> int:
    with _LOCK:
        return _EXPORT_CREDITS.get(str(email).strip().lower(), 0)
