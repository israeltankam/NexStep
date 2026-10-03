"""Edit an agent's profile and company-specific authority as one transaction."""

from __future__ import annotations

import re
import sqlite3

from database.connection import transaction
from database.repository import fetch_all, fetch_one, update_by_id
from services.audit_service import log_event
from utils.dates import utcnow_iso
from utils.security import hash_pin, normalize_pin, pin_lookup


AGENT_ROLES = ("agent", "manager", "company_admin")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def list_editable_agents(conn: sqlite3.Connection, *, actor_user_id: str) -> list[sqlite3.Row]:
    """Return company links, including disabled agents, for a global admin only."""
    actor = fetch_one(conn, "SELECT is_global_admin, is_active FROM users WHERE id = ?", (actor_user_id,))
    if not actor or not actor["is_global_admin"] or not actor["is_active"]:
        raise PermissionError("forbidden")
    return fetch_all(conn, """
        SELECT ou.id AS org_user_id, ou.organization_id, o.name AS organization_name,
               ou.user_id, ou.role, ou.can_view_team, ou.is_active AS link_active,
               u.display_name, u.email, u.phone, u.preferred_language,
               u.is_active AS account_active
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        JOIN organizations o ON o.id = ou.organization_id
        WHERE u.is_global_admin = 0 AND ou.role IN ('agent', 'manager', 'company_admin')
        ORDER BY o.name, u.display_name
    """)


def update_agent(conn: sqlite3.Connection, *, actor_user_id: str, org_user_id: str,
                 display_name: str, email: str, phone: str, preferred_language: str,
                 role: str, can_view_team: bool, account_active: bool,
                 link_active: bool, new_pin: str = "") -> None:
    """Save shared identity fields and one company's permissions atomically.

    A user may belong to several companies. Name, contact details, language and
    account status therefore follow the person; role, visibility, PIN and link
    status apply only to the selected company. Global-admin status is immutable.
    """
    actor = fetch_one(conn, "SELECT is_global_admin, is_active FROM users WHERE id = ?", (actor_user_id,))
    if not actor or not actor["is_global_admin"] or not actor["is_active"]:
        raise PermissionError("forbidden")
    target = fetch_one(conn, """
        SELECT ou.organization_id, ou.user_id, ou.role, u.is_global_admin
        FROM organization_users ou JOIN users u ON u.id = ou.user_id WHERE ou.id = ?
    """, (org_user_id,))
    if not target or target["is_global_admin"] or target["role"] not in AGENT_ROLES:
        raise ValueError("invalid_agent")
    name, mail, telephone = display_name.strip(), email.strip().lower(), phone.strip()
    if not name or len(name) > 200 or len(mail) > 254 or len(telephone) > 80 or (mail and not EMAIL_PATTERN.fullmatch(mail)):
        raise ValueError("invalid_agent_details")
    if preferred_language not in {"fr", "en"} or role not in AGENT_ROLES:
        raise ValueError("invalid_agent_details")
    if new_pin and (not normalize_pin(new_pin) or len(new_pin) > 128):
        raise ValueError("invalid_pin")
    if new_pin:
        duplicate = fetch_one(conn, """
            SELECT id FROM organization_users
            WHERE organization_id = ? AND agent_pin_lookup = ? AND id <> ?
        """, (target["organization_id"], pin_lookup(new_pin), org_user_id))
        if duplicate:
            raise ValueError("duplicate_pin")

    now = utcnow_iso()
    link_fields = {"role": role, "can_view_team": int(can_view_team or role == "company_admin"),
                   "is_active": int(link_active), "updated_at": now}
    if new_pin:
        link_fields.update(agent_pin_lookup=pin_lookup(new_pin), agent_pin_hash=hash_pin(new_pin))
    with transaction(conn):
        update_by_id(conn, "users", target["user_id"], {
            "display_name": name, "email": mail or None, "phone": telephone or None,
            "preferred_language": preferred_language, "is_active": int(account_active),
            "updated_at": now,
        })
        update_by_id(conn, "organization_users", org_user_id, link_fields)
        # Keep the audit useful without copying personal details or the secret PIN.
        log_event(conn, organization_id=target["organization_id"], actor_user_id=actor_user_id,
                  entity_type="organization_user", entity_id=org_user_id,
                  action="update_agent", after={"role": role, "can_view_team": bool(link_fields["can_view_team"]),
                  "link_active": link_active, "account_active": account_active,
                  "pin_changed": bool(new_pin)})
