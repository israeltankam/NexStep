"""Safely add the 2026-07-28 NexStep authentication tables to Supabase.

Usage from the NexStep project directory:

    python scripts/upgrade_supabase_20260728.py --check
    python scripts/upgrade_supabase_20260728.py --apply

``DATABASE_URL`` supplies the PostgreSQL connection. The script never prints
the URL and contains no destructive SQL.
"""

from __future__ import annotations

import argparse
import os
import sys

import psycopg
from psycopg.rows import dict_row


TABLE_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS public.auth_sessions (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES public.organizations(id),
        user_id TEXT NOT NULL REFERENCES public.users(id),
        org_user_id TEXT NOT NULL REFERENCES public.organization_users(id),
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used_at TEXT,
        revoked_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS public.password_reset_requests (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL REFERENCES public.organizations(id),
        user_id TEXT NOT NULL REFERENCES public.users(id),
        org_user_id TEXT NOT NULL REFERENCES public.organization_users(id),
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by_user_id TEXT REFERENCES public.users(id)
    )
    """,
)

INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON public.auth_sessions(token_hash)",
    """
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
    ON public.auth_sessions(org_user_id, revoked_at, expires_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_password_resets_org_status
    ON public.password_reset_requests(organization_id, status, requested_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_password_resets_user_status
    ON public.password_reset_requests(user_id, status)
    """,
)

TABLES = ("auth_sessions", "password_reset_requests")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add and verify NexStep authentication tables without changing existing data."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Verify only; make no change.")
    mode.add_argument("--apply", action="store_true", help="Create missing tables and secure them.")
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="Optional URL. Prefer DATABASE_URL to keep credentials out of shell history.",
    )
    return parser


def _normalize_url(database_url: str) -> str:
    """Accept SQLAlchemy-style URLs without importing the application."""

    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _connect(database_url: str):
    return psycopg.connect(
        _normalize_url(database_url),
        row_factory=dict_row,
        prepare_threshold=None,
        connect_timeout=10,
        sslmode="require",
        application_name="NexStep additive upgrade 20260728",
    )


def _apply(conn) -> None:
    """Run only reviewed, additive DDL inside one transaction."""

    for statement in TABLE_STATEMENTS:
        conn.execute(statement)
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)
    for table in TABLES:
        conn.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    conn.execute(
        """
        REVOKE ALL PRIVILEGES ON TABLE
            public.auth_sessions,
            public.password_reset_requests
        FROM anon, authenticated
        """
    )


def _audit(conn) -> list[dict[str, object]]:
    return list(
        conn.execute(
            """
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS rls_enabled,
                   has_table_privilege('anon', c.oid, 'SELECT')
                       OR has_table_privilege('anon', c.oid, 'INSERT')
                       OR has_table_privilege('anon', c.oid, 'UPDATE')
                       OR has_table_privilege('anon', c.oid, 'DELETE') AS anon_has_dml,
                   has_table_privilege('authenticated', c.oid, 'SELECT')
                       OR has_table_privilege('authenticated', c.oid, 'INSERT')
                       OR has_table_privilege('authenticated', c.oid, 'UPDATE')
                       OR has_table_privilege('authenticated', c.oid, 'DELETE')
                       AS authenticated_has_dml
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
              AND c.relname = ANY(%s)
            ORDER BY c.relname
            """,
            (list(TABLES),),
        ).fetchall()
    )


def _print_report(rows: list[dict[str, object]]) -> bool:
    by_name = {str(row["table_name"]): row for row in rows}
    all_secure = True
    for table in TABLES:
        row = by_name.get(table)
        secure = bool(
            row
            and row["rls_enabled"]
            and not row["anon_has_dml"]
            and not row["authenticated_has_dml"]
        )
        all_secure = all_secure and secure
        status = "OK" if secure else "MISSING OR INSECURE"
        print(f"[{status}] {table}")
    return all_secure


def main() -> int:
    args = _parser().parse_args()
    if not args.postgres_url:
        print("Error: DATABASE_URL is missing.", file=sys.stderr)
        return 2

    try:
        with _connect(args.postgres_url) as conn:
            if args.apply:
                _apply(conn)
            rows = _audit(conn)
    except Exception as exc:
        print(
            f"Supabase upgrade failed ({type(exc).__name__}). "
            "Check DATABASE_URL and PostgreSQL permissions.",
            file=sys.stderr,
        )
        return 2

    return 0 if _print_report(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
