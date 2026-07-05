"""Legacy import helpers.

The app can already accept tabular rows and preserve every raw field. Full Excel
upload support is enabled when pandas/openpyxl are installed from requirements.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from collections.abc import Iterable

from database.repository import fetch_one, insert
from services.comment_service import add_comment
from utils.dates import excel_serial_to_date, utcnow_iso
from utils.text import new_id, normalize_name
from utils.urgency import urgency_color


@dataclasses.dataclass
class ImportResult:
    imported_rows: int = 0
    skipped_rows: int = 0
    errors: list[str] = dataclasses.field(default_factory=list)
    legacy_comments: int = 0
    actions_without_due_date: int = 0


def import_legacy_rows(
    conn: sqlite3.Connection,
    rows: Iterable[dict[str, object]],
    *,
    organization_slug: str,
    source_filename: str,
    imported_by_user_id: str | None = None,
) -> ImportResult:
    """Import rows that follow the mapping in section 23 of the requirements."""

    organization = fetch_one(conn, "SELECT * FROM organizations WHERE slug = ?", (organization_slug,))
    if not organization:
        raise ValueError("Organization not found.")

    result = ImportResult()
    batch_id = new_id()
    prepared_rows = list(rows)
    insert(
        conn,
        "import_batches",
        {
            "id": batch_id,
            "organization_id": organization["id"],
            "source_filename": source_filename,
            "imported_by_user_id": imported_by_user_id,
            "row_count": len(prepared_rows),
            "imported_at": utcnow_iso(),
            "status": "completed",
            "notes": "Import manuel NexStep",
        },
    )
    for index, raw in enumerate(prepared_rows, start=5):
        name = str(raw.get("Lead") or raw.get("B") or "").strip()
        if not name:
            result.skipped_rows += 1
            continue
        try:
            lead_id = new_id()
            due_date = excel_serial_to_date(raw.get("Prochaine relance") or raw.get("F"))
            insert(
                conn,
                "leads",
                {
                    "id": lead_id,
                    "organization_id": organization["id"],
                    "name": name,
                    "normalized_name": normalize_name(name),
                    "owner_org_user_id": None,
                    "stage_id": None,
                    "status_id": None,
                    "category_id": None,
                    "city": raw.get("Ville"),
                    "address": None,
                    "latitude": None,
                    "longitude": None,
                    "score": float(raw.get("Score") or 0),
                    "source": "Excel legacy",
                    "source_detail": source_filename,
                    "obstacle": raw.get("Obstacle"),
                    "context_full": raw.get("Contexte complet"),
                    "prioritization_reason": raw.get("Pourquoi priorise"),
                    "churn_flag": 1 if str(raw.get("Churn", "")).casefold() == "oui" else 0,
                    "legacy_rank": raw.get("Rang"),
                    "legacy_row_number": index,
                    "legacy_age_days": raw.get("Age jours"),
                    "legacy_touchpoint_count": raw.get("Nb touchpoints"),
                    "legacy_fields_json": json.dumps(raw, ensure_ascii=False, default=str),
                    "possible_duplicate_group": None,
                    "is_archived": 0,
                    "created_at": utcnow_iso(),
                    "updated_at": utcnow_iso(),
                },
            )
            action_title = str(raw.get("Action") or "").strip()
            if action_title:
                insert(
                    conn,
                    "actions",
                    {
                        "id": new_id(),
                        "organization_id": organization["id"],
                        "lead_id": lead_id,
                        "assigned_to_org_user_id": None,
                        "created_by_org_user_id": None,
                        "action_type_id": None,
                        "title": action_title,
                        "details": raw.get("Nouvelle relance"),
                        "due_date": due_date,
                        "status": "pending",
                        "urgency_color_cache": urgency_color(due_date),
                        "completed_at": None,
                        "completed_by_org_user_id": None,
                        "completion_note": None,
                        "transferred_to_org_user_id": None,
                        "previous_action_id": None,
                        "created_at": utcnow_iso(),
                        "updated_at": utcnow_iso(),
                    },
                )
                if not due_date:
                    result.actions_without_due_date += 1
            legacy_comment = str(raw.get("a") or raw.get("J") or "").strip()
            if legacy_comment:
                add_comment(
                    conn,
                    organization_id=organization["id"],
                    lead_id=lead_id,
                    body=legacy_comment,
                    comment_type="legacy_excel_a",
                    visibility="team",
                    source="excel_import",
                    source_column="a",
                    is_system_import=True,
                )
                result.legacy_comments += 1
            insert(
                conn,
                "import_rows",
                {
                    "id": new_id(),
                    "import_batch_id": batch_id,
                    "lead_id": lead_id,
                    "excel_sheet": "Pipeline",
                    "excel_row_number": index,
                    "raw_json": json.dumps(raw, ensure_ascii=False, default=str),
                    "import_status": "imported",
                    "error_message": None,
                    "created_at": utcnow_iso(),
                },
            )
            result.imported_rows += 1
        except Exception as exc:  # keep importing and report row-level issues to the admin.
            result.errors.append(f"Ligne {index}: {exc}")
    conn.commit()
    return result


def read_uploaded_table(uploaded_file) -> list[dict[str, object]]:
    """Read CSV/XLSX uploads when optional spreadsheet dependencies are installed."""

    import pandas as pd

    name = uploaded_file.name.casefold()
    if name.endswith(".csv"):
        frame = pd.read_csv(uploaded_file)
    else:
        frame = pd.read_excel(uploaded_file, sheet_name="Pipeline", header=3)
    return frame.fillna("").to_dict(orient="records")
