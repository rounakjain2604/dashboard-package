"""Database configuration placeholders for the paid validation path.

Live Supabase/Postgres is intentionally not required for local readiness.
When DATABASE_URL is configured, production code can replace the in-memory
stores in usage.py with SQL-backed implementations using db/schema.sql.
"""
from __future__ import annotations

import os


def database_url() -> str | None:
    return os.environ.get("DATABASE_URL") or None


def using_live_database() -> bool:
    return bool(database_url())
