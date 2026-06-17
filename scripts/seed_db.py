"""Seed / initialize the Supabase persistent stores.

Prints the canonical SQL for the harness tables (Judgment Ledger, doctrine,
audit log) and, when Supabase is configured, verifies connectivity. Apply the
SQL via the Supabase SQL editor or ``psql`` before running in persistent mode.

Usage:
    python -m scripts.seed_db          # print schema SQL
    python -m scripts.seed_db --check  # also verify Supabase connectivity
"""

from __future__ import annotations

import sys
from pathlib import Path

from harness.config import get_settings

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "docker" / "supabase_schema.sql"


def print_schema() -> None:
    """Print the harness SQL schema to stdout."""
    if SCHEMA_PATH.exists():
        print(SCHEMA_PATH.read_text())
    else:  # pragma: no cover - defensive
        print(f"schema file not found at {SCHEMA_PATH}")


def check_connection() -> None:
    """Verify Supabase connectivity using configured credentials."""
    settings = get_settings()
    if not settings.supabase_enabled:
        print("Supabase is not configured (BLVCKSHELL_SUPABASE_URL/KEY). Skipping check.")
        return
    from supabase import create_client

    client = create_client(settings.supabase_url, settings.supabase_key)
    client.table("judgment_ledger").select("id").limit(1).execute()
    print("Supabase connection OK and judgment_ledger table reachable.")


if __name__ == "__main__":
    print_schema()
    if "--check" in sys.argv:
        check_connection()
