"""Audit or apply NexStep's Supabase Row-Level Security hardening.

Examples:
    python scripts/secure_supabase.py --check
    python scripts/secure_supabase.py --apply

The connection URL is read from ``DATABASE_URL`` by default so credentials do
not appear in shell history. The script never prints that URL.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection import normalize_postgres_url


NEXSTEP_TABLES = (
    "organizations",
    "users",
    "organization_users",
    "pipeline_stages",
    "lead_statuses",
    "client_categories",
    "action_types",
    "leads",
    "contacts",
    "actions",
    "touchpoints",
    "transfers",
    "comments",
    "import_batches",
    "import_rows",
    "auth_attempts",
    "audit_logs",
    "auth_sessions",
    "password_reset_requests",
)
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit or secure NexStep tables on Supabase.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read security state without changing it.")
    mode.add_argument("--apply", action="store_true", help="Enable RLS and revoke public API grants.")
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL"),
        help="Optional PostgreSQL URL; DATABASE_URL is safer because it avoids shell history.",
    )
    return parser


def _connect(database_url: str):
    return psycopg.connect(
        normalize_postgres_url(database_url),
        row_factory=dict_row,
        prepare_threshold=None,
        connect_timeout=10,
        sslmode="require",
        application_name="NexStep security audit",
    )


def _security_rows(conn) -> list[dict[str, object]]:
    """Return RLS and public grant state for only NexStep-owned tables."""

    rows = conn.execute(
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
                   OR has_table_privilege('authenticated', c.oid, 'DELETE') AS authenticated_has_dml
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND c.relname = ANY(%s)
        ORDER BY c.relname
        """,
        (list(NEXSTEP_TABLES),),
    ).fetchall()
    return list(rows)


def _apply_hardening(conn) -> None:
    """Apply the reviewed SQL policy one statement at a time.

    Executing separate statements works with direct, session-pooler, and
    transaction-pooler URLs. Identifiers are composed with Psycopg's SQL API so
    table names can never be interpreted as executable input.
    """

    for table in NEXSTEP_TABLES:
        conn.execute(
            sql.SQL("ALTER TABLE public.{} ENABLE ROW LEVEL SECURITY").format(sql.Identifier(table))
        )

    table_list = sql.SQL(", ").join(
        sql.SQL("public.{}").format(sql.Identifier(table)) for table in NEXSTEP_TABLES
    )
    conn.execute(
        sql.SQL("REVOKE ALL PRIVILEGES ON TABLE {} FROM anon, authenticated").format(table_list)
    )
    conn.execute(
        """
        ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
        REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated
        """
    )


def _print_report(rows: list[dict[str, object]]) -> bool:
    by_name = {str(row["table_name"]): row for row in rows}
    all_secure = True
    for table in NEXSTEP_TABLES:
        row = by_name.get(table)
        secure = bool(
            row
            and row["rls_enabled"]
            and not row["anon_has_dml"]
            and not row["authenticated_has_dml"]
        )
        all_secure = all_secure and secure
        status = "OK" if secure else "A CORRIGER"
        details = "RLS actif, aucun droit public" if secure else "RLS ou droits publics incorrects"
        print(f"[{status}] {table}: {details}")
    return all_secure


def main() -> int:
    args = _parser().parse_args()
    if not args.postgres_url:
        print("Erreur: DATABASE_URL est absent.", file=sys.stderr)
        return 2

    try:
        with _connect(args.postgres_url) as conn:
            if args.apply:
                _apply_hardening(conn)
            rows = _security_rows(conn)
    except Exception as exc:
        # Avoid echoing the URL while retaining the useful error class.
        print(f"Échec Supabase ({type(exc).__name__}). Vérifiez DATABASE_URL et les droits.", file=sys.stderr)
        return 2

    return 0 if _print_report(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
