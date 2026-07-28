"""Complete, super-admin-only database backup for disaster recovery."""

from __future__ import annotations

import csv
import io
import sqlite3
import zipfile
from collections.abc import Mapping

from database.repository import fetch_one
from database.schema import INDEX_STATEMENTS, SCHEMA_STATEMENTS
from utils.dates import utcnow_iso
from utils.paths import ROOT_DIR
from utils.security import verify_password


BACKUP_VERSION = "1"
NULL_MARKER = "__NEXSTEP_NULL__"

# This is deliberately the complete NexStep-owned database boundary. Unlike
# the company archive, it includes accounts, credential hashes, security
# events, access sessions and every organization.
FULL_BACKUP_TABLES = (
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


def verify_global_backup_authorization(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    password: str,
) -> bool:
    """Require an active global administrator and their current password."""

    user = fetch_one(
        conn,
        """
        SELECT password_hash, is_active, is_global_admin
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return bool(
        user
        and user["is_active"]
        and user["is_global_admin"]
        and verify_password(password, user["password_hash"])
    )


def _columns_and_rows(
    conn: sqlite3.Connection,
    table: str,
) -> tuple[tuple[str, ...], list[dict[str, object]]]:
    """Discover columns from the live database so future fields are not omitted."""

    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY id")
    columns = tuple(
        str(description.name if hasattr(description, "name") else description[0])
        for description in cursor.description
    )
    return columns, [dict(row) for row in cursor.fetchall()]


def _csv_content(
    columns: tuple[str, ...],
    rows: list[Mapping[str, object]],
) -> bytes:
    """Encode NULL explicitly so an empty string remains an empty string."""

    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                column: NULL_MARKER if row.get(column) is None else row.get(column)
                for column in columns
            }
        )
    return stream.getvalue().encode("utf-8-sig")


def _schema_snapshot() -> str:
    statements = [
        "-- NexStep schema snapshot included with the full database backup.",
        "-- Review this file before any disaster-recovery operation.",
        "",
    ]
    statements.extend(f"{statement.strip()};\n" for statement in SCHEMA_STATEMENTS)
    statements.extend(f"{statement.strip()};\n" for statement in INDEX_STATEMENTS)
    security_path = ROOT_DIR / "database" / "supabase_security.sql"
    if security_path.exists():
        statements.extend(
            [
                "",
                "-- Supabase RLS and public-grant hardening",
                security_path.read_text(encoding="utf-8"),
            ]
        )
    return "\n".join(statements)


def export_full_database_backup(conn: sqlite3.Connection) -> bytes:
    """Export every NexStep table, its live columns and a schema snapshot."""

    exported_at = utcnow_iso()
    table_payloads: dict[str, tuple[tuple[str, ...], list[dict[str, object]]]] = {}
    for table in FULL_BACKUP_TABLES:
        table_payloads[table] = _columns_and_rows(conn, table)

    manifest_rows = [
        {
            "backup_version": BACKUP_VERSION,
            "backup_type": "full_database",
            "exported_at": exported_at,
            "table_name": table,
            "row_count": len(table_payloads[table][1]),
            "null_marker": NULL_MARKER,
        }
        for table in FULL_BACKUP_TABLES
    ]
    manifest_columns = tuple(manifest_rows[0])

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.csv", _csv_content(manifest_columns, manifest_rows))
        archive.writestr("schema.sql", _schema_snapshot().encode("utf-8"))
        archive.writestr(
            "IMPORTANT_README.txt",
            (
                "NexStep full database backup\n"
                "============================\n\n"
                "This confidential archive contains every NexStep organization, user, "
                "business record, audit event and stored credential hash.\n"
                "It contains no plaintext PIN or password.\n\n"
                "APP_PIN_PEPPER is not stored in PostgreSQL and is therefore not included. "
                "Keep the exact Streamlit secret separately; restored PINs require it.\n"
                "Do not edit CSV files before a disaster-recovery operation.\n"
            ).encode("utf-8"),
        )
        for table, (columns, rows) in table_payloads.items():
            archive.writestr(f"tables/{table}.csv", _csv_content(columns, rows))
    return output.getvalue()
