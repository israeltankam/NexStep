"""Standalone SQLite to PostgreSQL migration runner for NexStep.

Examples:
    python scripts/migrate_sqlite_to_postgres.py --dry-run
    python scripts/migrate_sqlite_to_postgres.py --postgres-url "%DATABASE_URL%" --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.migration_service import migrate_sqlite_to_postgres
from utils.paths import get_database_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate NexStep from local SQLite to PostgreSQL.")
    parser.add_argument("--sqlite-path", default=str(get_database_path()), help="Path to the local SQLite database.")
    parser.add_argument("--postgres-url", default=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"), help="PostgreSQL/Supabase connection URL.")
    parser.add_argument("--dry-run", action="store_true", help="Read SQLite and print counts without writing to PostgreSQL. This is the default.")
    parser.add_argument("--apply", action="store_true", help="Write rows to PostgreSQL. Without this flag, only a dry-run report is produced.")
    parser.add_argument("--no-create-schema", action="store_true", help="Do not create PostgreSQL tables/indexes before inserting data.")
    parser.add_argument("--json", action="store_true", help="Print a JSON report.")
    return parser.parse_args()


def report_to_dict(report) -> dict[str, object]:
    return {
        "dry_run": report.dry_run,
        "sqlite_path": report.sqlite_path,
        "postgres_url_present": report.postgres_url_present,
        "table_counts": report.table_counts,
        "inserted_counts": report.inserted_counts,
        "skipped_counts": report.skipped_counts,
        "postgres_counts": report.postgres_counts,
        "errors": report.errors,
        "message": report.message,
    }


if __name__ == "__main__":
    args = parse_args()
    if args.apply and args.dry_run:
        raise SystemExit("Choisis soit --dry-run, soit --apply, pas les deux.")
    migration_report = migrate_sqlite_to_postgres(
        args.sqlite_path,
        args.postgres_url,
        dry_run=not args.apply,
        create_schema=not args.no_create_schema,
    )
    payload = report_to_dict(migration_report)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(migration_report.message)
        print(f"SQLite: {migration_report.sqlite_path}")
        print(f"PostgreSQL URL fourni: {'oui' if migration_report.postgres_url_present else 'non'}")
        for table, count in migration_report.table_counts.items():
            inserted = migration_report.inserted_counts.get(table, 0)
            skipped = migration_report.skipped_counts.get(table, 0)
            pg_count = migration_report.postgres_counts.get(table)
            suffix = f" | insérés: {inserted} | ignorés: {skipped}" if not migration_report.dry_run else ""
            if pg_count is not None:
                suffix += f" | PostgreSQL: {pg_count}"
            print(f"{table}: SQLite {count}{suffix}")
        if migration_report.errors:
            print("Écarts:")
            for error in migration_report.errors:
                print(f"- {error}")
