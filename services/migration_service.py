"""SQLite to PostgreSQL migration service for the local-to-cloud move."""

from __future__ import annotations

import dataclasses
import sqlite3
from pathlib import Path

from database.schema import INDEX_STATEMENTS, SCHEMA_STATEMENTS


MIGRATION_TABLES = [
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
    "audit_logs",
]


@dataclasses.dataclass
class MigrationReport:
    dry_run: bool
    sqlite_path: str
    postgres_url_present: bool
    table_counts: dict[str, int]
    message: str = ""
    inserted_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    skipped_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    postgres_counts: dict[str, int] = dataclasses.field(default_factory=dict)
    errors: list[str] = dataclasses.field(default_factory=list)


def _quote_identifier(identifier: str) -> str:
    """Quote trusted schema identifiers for PostgreSQL."""

    return '"' + identifier.replace('"', '""') + '"'


def _sqlite_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in MIGRATION_TABLES}


def _sqlite_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _connect_postgres(postgres_url: str):
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError("La dépendance psycopg est requise pour écrire vers PostgreSQL. Installe requirements.txt.") from exc
    connect_url = postgres_url.replace("postgresql+psycopg://", "postgresql://", 1)
    return psycopg.connect(connect_url)


def _create_postgres_schema(pg_conn) -> None:
    with pg_conn.cursor() as cur:
        for statement in SCHEMA_STATEMENTS:
            cur.execute(statement)
        for statement in INDEX_STATEMENTS:
            cur.execute(statement)


def _insert_table(sqlite_conn: sqlite3.Connection, pg_conn, table: str) -> tuple[int, int]:
    columns = _sqlite_columns(sqlite_conn, table)
    rows = sqlite_conn.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
    if not rows:
        return 0, 0

    quoted_table = _quote_identifier(table)
    quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
    placeholders = ", ".join(["%s"] * len(columns))
    conflict_clause = " ON CONFLICT (id) DO NOTHING"
    sql = f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders}){conflict_clause}"

    inserted = 0
    skipped = 0
    with pg_conn.cursor() as cur:
        for row in rows:
            cur.execute(sql, tuple(row[column] for column in columns))
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


def _postgres_counts(pg_conn) -> dict[str, int]:
    counts: dict[str, int] = {}
    with pg_conn.cursor() as cur:
        for table in MIGRATION_TABLES:
            cur.execute(f"SELECT COUNT(*) FROM {_quote_identifier(table)}")
            counts[table] = int(cur.fetchone()[0])
    return counts

def migrate_sqlite_to_postgres(
    sqlite_path: str,
    postgres_url: str | None = None,
    *,
    dry_run: bool = True,
    create_schema: bool = True,
) -> MigrationReport:
    """Migrate local SQLite rows to PostgreSQL, or produce a dry-run report."""

    path = Path(sqlite_path)
    if not path.exists():
        raise FileNotFoundError(sqlite_path)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        counts = _sqlite_counts(conn)
    finally:
        conn.close()

    if dry_run:
        return MigrationReport(
            dry_run=True,
            sqlite_path=str(path),
            postgres_url_present=bool(postgres_url),
            table_counts=counts,
            message="Dry run terminé: aucune écriture PostgreSQL effectuée.",
        )
    if not postgres_url:
        raise ValueError("postgres_url est requis quand dry_run=False.")

    sqlite_conn = sqlite3.connect(path)
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = _connect_postgres(postgres_url)
    inserted_counts: dict[str, int] = {}
    skipped_counts: dict[str, int] = {}
    try:
        with pg_conn.transaction():
            if create_schema:
                _create_postgres_schema(pg_conn)
            for table in MIGRATION_TABLES:
                inserted, skipped = _insert_table(sqlite_conn, pg_conn, table)
                inserted_counts[table] = inserted
                skipped_counts[table] = skipped
        postgres_counts = _postgres_counts(pg_conn)
    finally:
        sqlite_conn.close()
        pg_conn.close()

    mismatches = [
        f"{table}: SQLite={counts[table]}, PostgreSQL={postgres_counts.get(table, 0)}"
        for table in MIGRATION_TABLES
        if postgres_counts.get(table, 0) < counts[table]
    ]
    message = "Migration SQLite vers PostgreSQL terminée."
    if mismatches:
        message = "Migration terminée avec des écarts de vérification."
    return MigrationReport(
        dry_run=False,
        sqlite_path=str(path),
        postgres_url_present=True,
        table_counts=counts,
        inserted_counts=inserted_counts,
        skipped_counts=skipped_counts,
        postgres_counts=postgres_counts,
        errors=mismatches,
        message=message,
    )
