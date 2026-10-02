"""Contact creation for an existing prospect.

The creation flow can collect several contacts up front, but a real sales
relationship evolves over time.  This module keeps later additions out of the
page layer and applies the same rules to SQLite and PostgreSQL connections.
"""

from __future__ import annotations

import re
import sqlite3

from database.connection import transaction
from database.repository import fetch_one, insert, update_by_id
from services.audit_service import log_event
from utils.dates import utcnow_iso
from utils.text import new_id


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(value: str, maximum: int) -> str:
    """Trim a user-entered field and reject unexpectedly large payloads."""

    cleaned = str(value or "").strip()
    if len(cleaned) > maximum:
        raise ValueError("field_too_long")
    return cleaned


def _digits_only(value: str) -> str | None:
    """Build the searchable phone representation without altering display text."""

    digits = re.sub(r"\D+", "", value)
    return digits or None


def add_contact_to_lead(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    lead_id: str,
    actor_org_user_id: str,
    full_name: str = "",
    role_title: str = "",
    phone_raw: str = "",
    email: str = "",
    whatsapp: str = "",
    channel_notes: str = "",
) -> dict[str, object]:
    """Add one contact to an active lead belonging to the current organization.

    A name is not mandatory when a reliable channel such as a telephone number
    or e-mail address is known.  An entirely anonymous row, however, would not
    help an agent and is rejected before any database write.
    """

    contact = {
        "full_name": _clean(full_name, 200),
        "role_title": _clean(role_title, 200),
        "phone_raw": _clean(phone_raw, 80),
        "email": _clean(email, 254).casefold(),
        "whatsapp": _clean(whatsapp, 80),
        "channel_notes": _clean(channel_notes, 500),
    }
    if not any(contact[key] for key in ("full_name", "phone_raw", "email", "whatsapp")):
        raise ValueError("contact_required")
    if contact["email"] and not EMAIL_PATTERN.fullmatch(contact["email"]):
        raise ValueError("invalid_email")

    lead = fetch_one(
        conn,
        """
        SELECT id
        FROM leads
        WHERE id = ? AND organization_id = ? AND is_archived = 0
        """,
        (lead_id, organization_id),
    )
    if not lead:
        raise ValueError("lead_not_found")

    existing = fetch_one(
        conn,
        "SELECT COUNT(*) AS count FROM contacts WHERE lead_id = ?",
        (lead_id,),
    )
    is_primary = 1 if not existing or int(existing["count"]) == 0 else 0
    contact_id = new_id()
    now = utcnow_iso()

    with transaction(conn):
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
                "is_primary": is_primary,
                "created_at": now,
                "updated_at": now,
            },
        )
        update_by_id(conn, "leads", lead_id, {"updated_at": now})
        # Keep the event traceable without duplicating personal contact data in
        # the audit log or exposing it in a second database location.
        log_event(
            conn,
            organization_id=organization_id,
            actor_org_user_id=actor_org_user_id,
            entity_type="contact",
            entity_id=contact_id,
            action="add_contact_to_lead",
            after={"lead_id": lead_id, "is_primary": bool(is_primary)},
        )

    return {"contact_id": contact_id, "is_primary": bool(is_primary)}
