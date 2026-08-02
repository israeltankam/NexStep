"""User contact details with self-service and global-administrator scopes."""

from __future__ import annotations

import re
import sqlite3

from database.connection import transaction
from database.repository import fetch_one, update_by_id
from services.audit_service import log_event
from utils.dates import utcnow_iso


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean_contact_details(email: str, phone: str) -> tuple[str | None, str | None]:
    clean_email = email.strip().casefold()
    clean_phone = phone.strip()
    if clean_email and (len(clean_email) > 254 or not EMAIL_PATTERN.fullmatch(clean_email)):
        raise ValueError("invalid_email")
    if len(clean_phone) > 50:
        raise ValueError("invalid_phone")
    return clean_email or None, clean_phone or None


def get_user_contact_details(conn: sqlite3.Connection, user_id: str) -> dict[str, str]:
    user = fetch_one(
        conn,
        "SELECT email, phone FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    )
    if not user:
        raise ValueError("user_not_found")
    return {"email": str(user["email"] or ""), "phone": str(user["phone"] or "")}


def _update_contact_details(
    conn: sqlite3.Connection,
    *,
    target_user_id: str,
    email: str,
    phone: str,
    actor_user_id: str,
    organization_id: str | None,
    action: str,
) -> dict[str, str]:
    target = fetch_one(conn, "SELECT * FROM users WHERE id = ?", (target_user_id,))
    if not target:
        raise ValueError("user_not_found")
    clean_email, clean_phone = _clean_contact_details(email, phone)
    with transaction(conn):
        update_by_id(
            conn,
            "users",
            target_user_id,
            {"email": clean_email, "phone": clean_phone, "updated_at": utcnow_iso()},
        )
        # The audit records that contact channels changed without duplicating PII.
        log_event(
            conn,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            entity_type="user",
            entity_id=target_user_id,
            action=action,
            before={
                "email_set": bool(target["email"]),
                "phone_set": bool(target["phone"]),
            },
            after={"email_set": bool(clean_email), "phone_set": bool(clean_phone)},
        )
    return {"email": clean_email or "", "phone": clean_phone or ""}


def update_own_contact_details(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    organization_id: str,
    email: str,
    phone: str,
) -> dict[str, str]:
    """Let an active user edit only their own email and phone number."""

    return _update_contact_details(
        conn,
        target_user_id=user_id,
        email=email,
        phone=phone,
        actor_user_id=user_id,
        organization_id=organization_id,
        action="update_own_contact_details",
    )


def update_user_contact_details_as_global_admin(
    conn: sqlite3.Connection,
    *,
    target_user_id: str,
    email: str,
    phone: str,
    actor_user_id: str,
) -> dict[str, str]:
    """Allow only the active scale.ag global administrator to edit any user."""

    actor = fetch_one(
        conn,
        "SELECT is_global_admin FROM users WHERE id = ? AND is_active = 1",
        (actor_user_id,),
    )
    if not actor or not actor["is_global_admin"]:
        raise PermissionError("global_admin_required")
    return _update_contact_details(
        conn,
        target_user_id=target_user_id,
        email=email,
        phone=phone,
        actor_user_id=actor_user_id,
        organization_id=None,
        action="global_admin_update_contact_details",
    )
