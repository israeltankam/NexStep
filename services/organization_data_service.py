"""Safe CSV archive export and replacement for one organization's business data."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import zipfile
from collections.abc import Mapping

from database.connection import transaction
from database.repository import fetch_all, fetch_one, insert
from utils.dates import utcnow_iso
from utils.security import verify_password, verify_pin
from utils.text import new_id


ARCHIVE_VERSION = "1"
MAX_ARCHIVE_BYTES = 50 * 1024 * 1024

# Credentials, organizations, user accounts, access tokens, reset requests and
# audit logs are intentionally outside this replacement boundary.
TABLE_COLUMNS = {
    "pipeline_stages": (
        "id", "organization_id", "name", "position", "is_won", "is_lost",
        "is_active", "created_at",
    ),
    "lead_statuses": (
        "id", "organization_id", "name", "color_name", "position", "is_active",
        "created_at",
    ),
    "client_categories": (
        "id", "organization_id", "name", "description", "is_active", "created_at",
    ),
    "action_types": (
        "id", "organization_id", "name", "position", "is_active", "created_at",
    ),
    "leads": (
        "id", "organization_id", "name", "normalized_name", "owner_org_user_id",
        "stage_id", "status_id", "category_id", "city", "address", "latitude",
        "longitude", "score", "source", "source_detail", "obstacle", "context_full",
        "prioritization_reason", "churn_flag", "legacy_rank", "legacy_row_number",
        "legacy_age_days", "legacy_touchpoint_count", "legacy_fields_json",
        "possible_duplicate_group", "is_archived", "created_at", "updated_at",
    ),
    "contacts": (
        "id", "lead_id", "full_name", "role_title", "phone_raw", "phone_normalized",
        "email", "whatsapp", "channel_notes", "is_primary", "created_at", "updated_at",
    ),
    "actions": (
        "id", "organization_id", "lead_id", "assigned_to_org_user_id",
        "created_by_org_user_id", "action_type_id", "title", "details", "due_date",
        "status", "urgency_color_cache", "completed_at", "completed_by_org_user_id",
        "completion_note", "transferred_to_org_user_id", "previous_action_id",
        "created_at", "updated_at",
    ),
    "touchpoints": (
        "id", "organization_id", "lead_id", "action_id", "org_user_id", "contact_id",
        "occurred_at", "touchpoint_type", "channel", "outcome", "note",
        "decision_note", "action_note", "followup_note", "next_due_date", "source",
        "source_detail", "legacy_update_at", "created_at",
    ),
    "transfers": (
        "id", "organization_id", "lead_id", "action_id", "from_org_user_id",
        "to_org_user_id", "transfer_note", "created_at",
    ),
    "comments": (
        "id", "organization_id", "lead_id", "action_id", "touchpoint_id",
        "transfer_id", "org_user_id", "body", "comment_type", "visibility", "source",
        "source_column", "is_pinned", "is_system_import", "created_at", "updated_at",
    ),
    "import_batches": (
        "id", "organization_id", "source_filename", "imported_by_user_id",
        "row_count", "imported_at", "status", "notes",
    ),
    "import_rows": (
        "id", "import_batch_id", "lead_id", "excel_sheet", "excel_row_number",
        "raw_json", "import_status", "error_message", "created_at",
    ),
}

INSERT_ORDER = (
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
)

DELETE_ORDER = (
    "comments",
    "transfers",
    "touchpoints",
    "actions",
    "contacts",
    "import_rows",
    "leads",
    "import_batches",
    "action_types",
    "client_categories",
    "lead_statuses",
    "pipeline_stages",
)

INTEGER_COLUMNS = {
    "position", "is_won", "is_lost", "is_active", "churn_flag",
    "legacy_row_number", "legacy_age_days", "legacy_touchpoint_count",
    "is_archived", "is_primary", "is_pinned", "is_system_import", "row_count",
    "excel_row_number",
}
FLOAT_COLUMNS = {"latitude", "longitude", "score", "legacy_rank"}


def _organization_rows(
    conn: sqlite3.Connection,
    table: str,
    organization_id: str,
) -> list[dict[str, object]]:
    """Read only rows belonging to the requested organization."""

    if table in {"contacts"}:
        query = (
            f"SELECT c.* FROM {table} c JOIN leads l ON l.id = c.lead_id "
            "WHERE l.organization_id = ?"
        )
    elif table == "import_rows":
        query = (
            "SELECT ir.* FROM import_rows ir "
            "JOIN import_batches ib ON ib.id = ir.import_batch_id "
            "WHERE ib.organization_id = ?"
        )
    else:
        query = f"SELECT * FROM {table} WHERE organization_id = ?"
    return [dict(row) for row in fetch_all(conn, query, (organization_id,))]


def _csv_bytes(columns: tuple[str, ...], rows: list[Mapping[str, object]]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in columns})
    return stream.getvalue().encode("utf-8-sig")


def export_organization_csv_archive(
    conn: sqlite3.Connection,
    organization_id: str,
) -> bytes:
    """Export one organization's business records as related CSV files."""

    organization = fetch_one(
        conn,
        "SELECT id, name, display_name, slug FROM organizations WHERE id = ?",
        (organization_id,),
    )
    if not organization:
        raise ValueError("organization_not_found")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        manifest = [
            {
                "archive_version": ARCHIVE_VERSION,
                "organization_id": organization["id"],
                "organization_name": organization["display_name"] or organization["name"],
                "organization_slug": organization["slug"],
                "exported_at": utcnow_iso(),
            }
        ]
        archive.writestr(
            "manifest.csv",
            _csv_bytes(tuple(manifest[0].keys()), manifest),
        )
        for table, columns in TABLE_COLUMNS.items():
            archive.writestr(
                f"{table}.csv",
                _csv_bytes(columns, _organization_rows(conn, table, organization_id)),
            )
    return output.getvalue()


def _read_csv(archive: zipfile.ZipFile, table: str) -> list[dict[str, object]]:
    filename = f"{table}.csv"
    if filename not in archive.namelist():
        raise ValueError(f"missing_file:{filename}")
    content = archive.read(filename).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    expected = set(TABLE_COLUMNS[table])
    if not reader.fieldnames or set(reader.fieldnames) != expected:
        raise ValueError(f"invalid_columns:{filename}")
    rows: list[dict[str, object]] = []
    for source_row in reader:
        row: dict[str, object] = {}
        for column in TABLE_COLUMNS[table]:
            value = source_row.get(column, "")
            if value == "":
                row[column] = None
            elif column in INTEGER_COLUMNS:
                row[column] = int(value)
            elif column in FLOAT_COLUMNS:
                row[column] = float(value)
            else:
                row[column] = value
        rows.append(row)
    return rows


def parse_organization_csv_archive(
    file_content: bytes,
    expected_organization_id: str,
) -> dict[str, list[dict[str, object]]]:
    """Parse and validate every file before any database transaction starts."""

    if not file_content or len(file_content) > MAX_ARCHIVE_BYTES:
        raise ValueError("invalid_archive_size")
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
            if "manifest.csv" not in archive.namelist():
                raise ValueError("missing_manifest")
            manifest_rows = list(
                csv.DictReader(io.StringIO(archive.read("manifest.csv").decode("utf-8-sig")))
            )
            if len(manifest_rows) != 1:
                raise ValueError("invalid_manifest")
            manifest = manifest_rows[0]
            if manifest.get("archive_version") != ARCHIVE_VERSION:
                raise ValueError("unsupported_archive_version")
            if manifest.get("organization_id") != expected_organization_id:
                raise ValueError("wrong_organization")
            data = {table: _read_csv(archive, table) for table in TABLE_COLUMNS}
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid_archive") from exc

    _validate_archive_references(data, expected_organization_id)
    return data


def _ids(rows: list[dict[str, object]]) -> set[str]:
    values = [str(row["id"]) for row in rows if row.get("id")]
    if len(values) != len(set(values)):
        raise ValueError("duplicate_ids")
    return set(values)


def _require_reference(
    rows: list[dict[str, object]],
    column: str,
    allowed: set[str],
    error: str,
) -> None:
    if any(row.get(column) is not None and str(row[column]) not in allowed for row in rows):
        raise ValueError(error)


def _validate_archive_references(
    data: dict[str, list[dict[str, object]]],
    organization_id: str,
) -> None:
    """Reject cross-company rows and broken relations before replacement."""

    for table, rows in data.items():
        if "organization_id" in TABLE_COLUMNS[table] and any(
            str(row.get("organization_id")) != organization_id for row in rows
        ):
            raise ValueError(f"cross_organization_row:{table}")

    ids = {table: _ids(rows) for table, rows in data.items()}
    _require_reference(data["leads"], "stage_id", ids["pipeline_stages"], "invalid_stage")
    _require_reference(data["leads"], "status_id", ids["lead_statuses"], "invalid_status")
    _require_reference(data["leads"], "category_id", ids["client_categories"], "invalid_category")
    for table in ("contacts", "actions", "touchpoints", "transfers", "comments"):
        _require_reference(data[table], "lead_id", ids["leads"], f"invalid_lead:{table}")
    _require_reference(data["actions"], "action_type_id", ids["action_types"], "invalid_action_type")
    _require_reference(data["actions"], "previous_action_id", ids["actions"], "invalid_previous_action")
    _require_reference(data["touchpoints"], "action_id", ids["actions"], "invalid_touchpoint_action")
    _require_reference(data["touchpoints"], "contact_id", ids["contacts"], "invalid_touchpoint_contact")
    _require_reference(data["transfers"], "action_id", ids["actions"], "invalid_transfer_action")
    _require_reference(data["comments"], "action_id", ids["actions"], "invalid_comment_action")
    _require_reference(data["comments"], "touchpoint_id", ids["touchpoints"], "invalid_comment_touchpoint")
    _require_reference(data["comments"], "transfer_id", ids["transfers"], "invalid_comment_transfer")
    _require_reference(data["import_rows"], "import_batch_id", ids["import_batches"], "invalid_import_batch")
    _require_reference(data["import_rows"], "lead_id", ids["leads"], "invalid_import_lead")


def verify_replacement_authorization(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    user_id: str,
    company_pins: tuple[str, str, str],
    password: str,
) -> bool:
    """Require three matching valid company PIN entries and the admin password."""

    organization = fetch_one(
        conn,
        "SELECT company_pin_hash FROM organizations WHERE id = ? AND is_active = 1",
        (organization_id,),
    )
    user = fetch_one(
        conn,
        "SELECT password_hash FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    )
    if not organization or not user or len(set(company_pins)) != 1:
        return False
    return all(verify_pin(pin, organization["company_pin_hash"]) for pin in company_pins) and verify_password(
        password, user["password_hash"]
    )


def replace_organization_business_data(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    actor_user_id: str,
    archive_data: dict[str, list[dict[str, object]]],
) -> dict[str, int]:
    """Atomically replace only the validated business-data boundary."""

    _validate_archive_references(archive_data, organization_id)
    existing_org_users = {
        str(row["id"])
        for row in fetch_all(
            conn,
            "SELECT id FROM organization_users WHERE organization_id = ?",
            (organization_id,),
        )
    }
    user_reference_columns = {
        "leads": ("owner_org_user_id",),
        "actions": (
            "assigned_to_org_user_id",
            "created_by_org_user_id",
            "completed_by_org_user_id",
            "transferred_to_org_user_id",
        ),
        "touchpoints": ("org_user_id",),
        "transfers": ("from_org_user_id", "to_org_user_id"),
        "comments": ("org_user_id",),
    }
    for table, columns in user_reference_columns.items():
        for column in columns:
            _require_reference(
                archive_data[table],
                column,
                existing_org_users,
                f"unknown_team_member:{table}.{column}",
            )

    counts = {table: len(rows) for table, rows in archive_data.items()}
    now = utcnow_iso()
    with transaction(conn):
        lead_ids = [
            str(row["id"])
            for row in fetch_all(conn, "SELECT id FROM leads WHERE organization_id = ?", (organization_id,))
        ]
        batch_ids = [
            str(row["id"])
            for row in fetch_all(
                conn,
                "SELECT id FROM import_batches WHERE organization_id = ?",
                (organization_id,),
            )
        ]
        for table in DELETE_ORDER:
            if table == "contacts":
                _delete_by_ids(conn, table, "lead_id", lead_ids)
            elif table == "import_rows":
                _delete_by_ids(conn, table, "import_batch_id", batch_ids)
            else:
                conn.execute(f"DELETE FROM {table} WHERE organization_id = ?", (organization_id,))

        previous_links: list[tuple[str, str]] = []
        for table in INSERT_ORDER:
            for source_row in archive_data[table]:
                row = dict(source_row)
                if table == "actions" and row.get("previous_action_id"):
                    previous_links.append((str(row["id"]), str(row["previous_action_id"])))
                    row["previous_action_id"] = None
                insert(conn, table, row)
        for action_id, previous_action_id in previous_links:
            conn.execute(
                "UPDATE actions SET previous_action_id = ? WHERE id = ?",
                (previous_action_id, action_id),
            )
        insert(
            conn,
            "audit_logs",
            {
                "id": new_id(),
                "organization_id": organization_id,
                "actor_user_id": actor_user_id,
                "actor_org_user_id": None,
                "entity_type": "organization_business_data",
                "entity_id": organization_id,
                "action": "replace_from_csv_archive",
                "before_json": None,
                "after_json": json.dumps(counts, sort_keys=True),
                "created_at": now,
            },
        )
    return counts


def _delete_by_ids(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    row_ids: list[str],
) -> None:
    if not row_ids:
        return
    placeholders = ", ".join("?" for _ in row_ids)
    conn.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", tuple(row_ids))
