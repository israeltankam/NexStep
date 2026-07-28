"""Manual lead creation with an immediate first action.

This service is deliberately small and transactional: when an agent creates a
lead, NexStep must either save the lead, optional contact, optional comment and
first action together, or save nothing. That keeps the agent interface simple
without creating half-complete customer files in the database.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping, Sequence

from database.connection import transaction
from database.repository import fetch_one, insert
from services.comment_service import add_comment
from utils.dates import utcnow_iso
from utils.text import new_id, normalize_name, slugify
from utils.urgency import urgency_color


REFERENCE_TABLES = {"pipeline_stages", "lead_statuses", "client_categories", "action_types"}


def _digits_only(value: str) -> str | None:
    """Normalize a phone number enough for matching while preserving the raw text."""

    digits = re.sub(r"\D+", "", value or "")
    return digits or None


def _reference_order(table: str) -> str:
    """Return the safe ORDER BY clause for each reference table.

    Most reference tables have a `position` column, but client categories do not.
    Keeping the difference here prevents UI code from knowing schema details.
    """

    return "name ASC" if table == "client_categories" else "position ASC, name ASC"


def _reference_id(
    conn: sqlite3.Connection,
    organization_id: str,
    table: str,
    preferred_name: str | None,
    *,
    fallback_name: str | None = None,
) -> str | None:
    """Resolve a reference row by name, with an active-row fallback."""

    if table not in REFERENCE_TABLES:
        raise ValueError("Unsupported reference table.")
    for name in (preferred_name, fallback_name):
        if not name:
            continue
        row = fetch_one(
            conn,
            f"SELECT id FROM {table} WHERE organization_id = ? AND name = ? AND is_active = 1",
            (organization_id, name),
        )
        if row:
            return row["id"]
    row = fetch_one(
        conn,
        f"""
        SELECT id
        FROM {table}
        WHERE organization_id = ? AND is_active = 1
        ORDER BY {_reference_order(table)}
        LIMIT 1
        """,
        (organization_id,),
    )
    return row["id"] if row else None


def _duplicate_group(conn: sqlite3.Connection, organization_id: str, normalized_name: str, lead_name: str) -> str | None:
    """Attach a duplicate group only when a similar lead already exists."""

    if not normalized_name:
        return None
    existing = fetch_one(
        conn,
        "SELECT id FROM leads WHERE organization_id = ? AND normalized_name = ? LIMIT 1",
        (organization_id, normalized_name),
    )
    return slugify(lead_name) or normalized_name.replace(" ", "-") if existing else None


def create_lead_with_first_action(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    actor_org_user_id: str,
    lead_name: str,
    category_name: str | None = None,
    contact_name: str = "",
    phone_raw: str = "",
    channel_notes: str = "",
    contacts: Sequence[Mapping[str, object]] | None = None,
    city: str = "",
    context_note: str = "",
    action_type_name: str | None = "Appel",
    action_title: str | None = None,
    due_date: str | None = None,
    action_details: str = "",
) -> dict[str, object]:
    """Create a lead owned by the current agent and queue its first action."""

    cleaned_name = lead_name.strip()
    if not cleaned_name:
        raise ValueError("lead_name_required")

    now = utcnow_iso()
    normalized = normalize_name(cleaned_name)
    contact_ids: list[str] = []
    comment_id = None
    supplied_contacts = list(contacts) if contacts is not None else [
        {
            "full_name": contact_name,
            "phone_raw": phone_raw,
            "channel_notes": channel_notes,
        }
    ]

    with transaction(conn):
        lead_id = new_id()
        action_id = new_id()
        stage_id = _reference_id(conn, organization_id, "pipeline_stages", "Nouveau lead")
        status_id = _reference_id(conn, organization_id, "lead_statuses", "Nouveau")
        category_id = _reference_id(conn, organization_id, "client_categories", category_name) if category_name else None
        action_type_id = _reference_id(conn, organization_id, "action_types", action_type_name, fallback_name="Appel")

        insert(
            conn,
            "leads",
            {
                "id": lead_id,
                "organization_id": organization_id,
                "name": cleaned_name,
                "normalized_name": normalized,
                "owner_org_user_id": actor_org_user_id,
                "stage_id": stage_id,
                "status_id": status_id,
                "category_id": category_id,
                "city": city.strip() or None,
                "address": None,
                "latitude": None,
                "longitude": None,
                "score": 0.0,
                "source": "manual",
                "source_detail": "NexStep agent",
                "obstacle": None,
                "context_full": context_note.strip() or None,
                "prioritization_reason": None,
                "churn_flag": 0,
                "legacy_rank": None,
                "legacy_row_number": None,
                "legacy_age_days": None,
                "legacy_touchpoint_count": None,
                "legacy_fields_json": json.dumps(
                    {"created_from": "new_lead_form", "created_by_org_user_id": actor_org_user_id},
                    ensure_ascii=False,
                ),
                "possible_duplicate_group": _duplicate_group(conn, organization_id, normalized, cleaned_name),
                "is_archived": 0,
                "created_at": now,
                "updated_at": now,
            },
        )

        for contact_index, supplied_contact in enumerate(supplied_contacts):
            contact = {
                key: str(supplied_contact.get(key) or "").strip()
                for key in (
                    "full_name",
                    "role_title",
                    "phone_raw",
                    "email",
                    "whatsapp",
                    "channel_notes",
                )
            }
            if contact_index == 0 and channel_notes.strip() and not contact["channel_notes"]:
                contact["channel_notes"] = channel_notes.strip()
            if not any(contact.values()):
                continue

            contact_id = new_id()
            contact_ids.append(contact_id)
            insert(
                conn,
                "contacts",
                {
                    "id": contact_id,
                    "lead_id": lead_id,
                    "full_name": contact["full_name"] or None,
                    "role_title": contact["role_title"] or None,
                    "phone_raw": contact["phone_raw"] or None,
                    "phone_normalized": _digits_only(contact["phone_raw"]),
                    "email": contact["email"] or None,
                    "whatsapp": contact["whatsapp"] or None,
                    "channel_notes": contact["channel_notes"] or None,
                    "is_primary": 1 if len(contact_ids) == 1 else 0,
                    "created_at": now,
                    "updated_at": now,
                },
            )

        insert(
            conn,
            "actions",
            {
                "id": action_id,
                "organization_id": organization_id,
                "lead_id": lead_id,
                "assigned_to_org_user_id": actor_org_user_id,
                "created_by_org_user_id": actor_org_user_id,
                "action_type_id": action_type_id,
                "title": (action_title or action_type_name or "Première action").strip(),
                "details": action_details.strip() or None,
                "due_date": due_date,
                "status": "pending",
                "urgency_color_cache": urgency_color(due_date),
                "completed_at": None,
                "completed_by_org_user_id": None,
                "completion_note": None,
                "transferred_to_org_user_id": None,
                "previous_action_id": None,
                "created_at": now,
                "updated_at": now,
            },
        )

        comment_parts = [part.strip() for part in (context_note, action_details) if part and part.strip()]
        if comment_parts:
            comment_id = add_comment(
                conn,
                organization_id=organization_id,
                lead_id=lead_id,
                action_id=action_id,
                org_user_id=actor_org_user_id,
                body="\n\n".join(comment_parts),
                comment_type="general",
                source="manual",
            )

    return {
        "lead_id": lead_id,
        "action_id": action_id,
        "contact_id": contact_ids[0] if contact_ids else None,
        "contact_ids": contact_ids,
        "comment_id": comment_id,
    }
