"""Minimal email/token identification for local paid-validation gating."""
from __future__ import annotations

import os


def identify_user(headers, payload: dict | None = None) -> dict:
    payload = payload or {}
    email = (
        headers.get("X-Trinsic-Email")
        or payload.get("email")
        or payload.get("user_email")
        or ""
    ).strip().lower()
    anonymous_id = (
        headers.get("X-Trinsic-Anonymous-Id")
        or payload.get("anonymous_id")
        or ""
    ).strip()
    token = headers.get("X-Trinsic-Export-Token") or payload.get("export_token") or ""
    dev_token = os.environ.get("TRINSIC_DEV_EXPORT_TOKEN", "dev-export-credit")
    token_valid = bool(token) and token == dev_token and os.environ.get("APP_ENV", "development") != "production"
    return {
        "email": email or None,
        "anonymous_id": anonymous_id or None,
        "token_valid": token_valid,
    }
