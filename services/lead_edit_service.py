"""Password-confirmed edits of lead identity and existing contact details."""

from __future__ import annotations

import re

from database.connection import transaction
from database.repository import fetch_one, update_by_id
from services.audit_service import log_event
from services.auth_service import verify_user_password
from services.lead_permissions import editable_lead
from utils.dates import utcnow_iso


def update_lead_details(conn, *, lead_id: str, actor_org_user_id: str,
                        password: str, name: str, city: str, context_full: str,
                        contacts: list[dict[str, str]]) -> None:
    """Apply one atomic edit after checking ownership and the current password."""
    lead = editable_lead(conn, lead_id, actor_org_user_id)
    actor = fetch_one(conn, """SELECT u.* FROM users u JOIN organization_users ou
        ON ou.user_id = u.id WHERE ou.id = ?""", (actor_org_user_id,))
    if not actor or not verify_user_password(actor, password):
        raise ValueError("invalid_password")
    clean_name = name.strip()
    if not clean_name or len(clean_name) > 200:
        raise ValueError("invalid_name")
    if len(city) > 200 or len(context_full) > 5000:
        raise ValueError("field_too_long")
    existing = {row["id"]: row for row in conn.execute(
        "SELECT * FROM contacts WHERE lead_id = ?", (lead_id,)).fetchall()}
    if len(contacts) != len(existing) or {item.get("id") for item in contacts} != set(existing):
        raise ValueError("contact_mismatch")
    cleaned = []
    for item in contacts:
        fields = {key: str(item.get(key) or "").strip() for key in
                  ("full_name", "role_title", "phone_raw", "email", "whatsapp", "channel_notes")}
        if any(len(fields[key]) > limit for key, limit in {
            "full_name": 200, "role_title": 200, "phone_raw": 80,
            "email": 254, "whatsapp": 80, "channel_notes": 500}.items()):
            raise ValueError("field_too_long")
        if fields["email"] and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", fields["email"]):
            raise ValueError("invalid_email")
        fields["email"] = fields["email"].casefold()
        fields["phone_normalized"] = re.sub(r"\D+", "", fields["phone_raw"]) or None
        cleaned.append((item["id"], fields))
    now = utcnow_iso()
    with transaction(conn):
        update_by_id(conn, "leads", lead_id, {
            "name": clean_name, "normalized_name": " ".join(clean_name.casefold().split()),
            "city": city.strip() or None, "context_full": context_full.strip() or None,
            "updated_at": now})
        for contact_id, fields in cleaned:
            update_by_id(conn, "contacts", contact_id, {
                **{key: value or None for key, value in fields.items()}, "updated_at": now})
        # Audit the changed entity without copying personal data into the log.
        log_event(conn, organization_id=lead["organization_id"],
                  actor_org_user_id=actor_org_user_id, entity_type="lead",
                  entity_id=lead_id, action="edit_details",
                  after={"contact_count": len(cleaned)})
