"""Admin operations for organizations, users, links, PIN updates, and logs."""

from __future__ import annotations

import sqlite3

from database.connection import transaction
from database.repository import fetch_all, fetch_one, insert, update_by_id
from services.audit_service import log_event
from utils.dates import utcnow_iso
from utils.security import hash_pin, pin_lookup
from utils.text import new_id, slugify


def list_organizations(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return fetch_all(conn, "SELECT id, name, slug, display_name, default_language, client_label, is_active, created_at FROM organizations ORDER BY name")


def list_users(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        "SELECT id, display_name, email, phone, preferred_language, is_active, is_global_admin, created_at FROM users ORDER BY display_name",
    )


def list_org_links(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        """
        SELECT ou.id, o.name AS organization_name, u.display_name, ou.role, ou.can_view_team, ou.is_active, ou.created_at
        FROM organization_users ou
        JOIN organizations o ON o.id = ou.organization_id
        JOIN users u ON u.id = ou.user_id
        ORDER BY o.name, u.display_name
        """,
    )


def create_organization(
    conn: sqlite3.Connection,
    *,
    name: str,
    slug: str,
    company_pin: str,
    default_language: str,
    client_label: str,
    is_active: bool,
    actor_user_id: str | None = None,
) -> str:
    clean_slug = slug.strip() or slugify(name)
    organization_id = new_id()
    now = utcnow_iso()
    with transaction(conn):
        insert(
            conn,
            "organizations",
            {
                "id": organization_id,
                "name": name.strip(),
                "slug": clean_slug,
                "display_name": name.strip(),
                "company_pin_lookup": pin_lookup(company_pin),
                "company_pin_hash": hash_pin(company_pin),
                "default_language": default_language,
                "client_label": client_label.strip() or "Client",
                "is_active": 1 if is_active else 0,
                "created_at": now,
                "updated_at": now,
            },
        )
        log_event(conn, entity_type="organization", entity_id=organization_id, action="create", actor_user_id=actor_user_id)
    return organization_id


def create_user(
    conn: sqlite3.Connection,
    *,
    display_name: str,
    email: str | None,
    phone: str | None,
    preferred_language: str,
    is_active: bool,
    actor_user_id: str | None = None,
) -> str:
    user_id = new_id()
    now = utcnow_iso()
    with transaction(conn):
        insert(
            conn,
            "users",
            {
                "id": user_id,
                "display_name": display_name.strip(),
                "email": email.strip() if email else None,
                "phone": phone.strip() if phone else None,
                "password_hash": None,
                "password_set_at": None,
                "must_change_password": 0,
                "preferred_language": preferred_language,
                "is_active": 1 if is_active else 0,
                "is_global_admin": 0,
                "created_at": now,
                "updated_at": now,
            },
        )
        log_event(conn, entity_type="user", entity_id=user_id, action="create", actor_user_id=actor_user_id)
    return user_id


def link_user_to_organization(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    user_id: str,
    agent_pin: str,
    role: str,
    can_view_team: bool,
    actor_user_id: str | None = None,
) -> str:
    link_id = new_id()
    now = utcnow_iso()
    with transaction(conn):
        insert(
            conn,
            "organization_users",
            {
                "id": link_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "agent_pin_lookup": pin_lookup(agent_pin),
                "agent_pin_hash": hash_pin(agent_pin),
                "role": role,
                "can_view_team": 1 if can_view_team else 0,
                "is_active": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        log_event(conn, organization_id=organization_id, entity_type="organization_user", entity_id=link_id, action="link_user", actor_user_id=actor_user_id)
    return link_id


def update_company_pin(conn: sqlite3.Connection, organization_id: str, new_pin: str, *, actor_user_id: str | None = None) -> None:
    with transaction(conn):
        update_by_id(
            conn,
            "organizations",
            organization_id,
            {
                "company_pin_lookup": pin_lookup(new_pin),
                "company_pin_hash": hash_pin(new_pin),
                "updated_at": utcnow_iso(),
            },
        )
        log_event(conn, organization_id=organization_id, entity_type="organization", entity_id=organization_id, action="update_company_pin", actor_user_id=actor_user_id)


def update_agent_pin(conn: sqlite3.Connection, org_user_id: str, new_pin: str, *, actor_user_id: str | None = None) -> None:
    link = fetch_one(conn, "SELECT * FROM organization_users WHERE id = ?", (org_user_id,))
    if not link:
        raise ValueError("Organization-user link not found.")
    with transaction(conn):
        update_by_id(
            conn,
            "organization_users",
            org_user_id,
            {
                "agent_pin_lookup": pin_lookup(new_pin),
                "agent_pin_hash": hash_pin(new_pin),
                "updated_at": utcnow_iso(),
            },
        )
        log_event(conn, organization_id=link["organization_id"], entity_type="organization_user", entity_id=org_user_id, action="update_agent_pin", actor_user_id=actor_user_id)


def recent_audit_logs(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        """
        SELECT al.*, u.display_name AS actor_name, o.name AS organization_name
        FROM audit_logs al
        LEFT JOIN users u ON u.id = al.actor_user_id
        LEFT JOIN organizations o ON o.id = al.organization_id
        ORDER BY al.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
