"""Authentication service for two-PIN identification and password login."""

from __future__ import annotations

import dataclasses
import sqlite3

from database.repository import fetch_one, insert, update_by_id
from utils.dates import utcnow_iso
from utils.security import hash_password, pin_lookup, verify_password, verify_pin
from utils.text import new_id


@dataclasses.dataclass(frozen=True)
class AuthResult:
    ok: bool
    message_key: str
    organization: sqlite3.Row | None = None
    user: sqlite3.Row | None = None
    org_user: sqlite3.Row | None = None


def _log_attempt(
    conn: sqlite3.Connection,
    *,
    organization_lookup: str | None,
    agent_lookup: str | None,
    success: bool,
    failure_reason: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    insert(
        conn,
        "auth_attempts",
        {
            "id": new_id(),
            "organization_lookup": organization_lookup,
            "agent_lookup": agent_lookup,
            "success": 1 if success else 0,
            "failure_reason": failure_reason,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": utcnow_iso(),
        },
    )


def _recent_failures(conn: sqlite3.Connection, organization_lookup: str, agent_lookup: str) -> int:
    row = fetch_one(
        conn,
        """
        SELECT COUNT(*) AS count
        FROM auth_attempts
        WHERE organization_lookup = ?
          AND agent_lookup = ?
          AND success = 0
          AND created_at >= datetime('now', '-15 minutes')
        """,
        (organization_lookup, agent_lookup),
    )
    return int(row["count"] if row else 0)


def identify_by_pins(
    conn: sqlite3.Connection,
    company_pin: str,
    agent_pin: str,
    *,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthResult:
    """Identify the organization-user relation without revealing which PIN failed."""

    company_lookup = pin_lookup(company_pin)
    agent_lookup = pin_lookup(agent_pin)
    if _recent_failures(conn, company_lookup, agent_lookup) >= 5:
        _log_attempt(
            conn,
            organization_lookup=company_lookup,
            agent_lookup=agent_lookup,
            success=False,
            failure_reason="too_many_attempts",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.commit()
        return AuthResult(False, "login.too_many_attempts")

    organization = fetch_one(
        conn,
        "SELECT * FROM organizations WHERE company_pin_lookup = ?",
        (company_lookup,),
    )
    if not organization or not organization["is_active"] or not verify_pin(company_pin, organization["company_pin_hash"]):
        _log_attempt(
            conn,
            organization_lookup=company_lookup,
            agent_lookup=agent_lookup,
            success=False,
            failure_reason="invalid_credentials",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.commit()
        return AuthResult(False, "login.invalid_credentials")

    org_user = fetch_one(
        conn,
        """
        SELECT ou.*, u.display_name, u.email, u.phone, u.password_hash, u.password_set_at,
               u.must_change_password, u.preferred_language, u.is_active AS user_is_active,
               u.is_global_admin
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.organization_id = ?
          AND ou.agent_pin_lookup = ?
        """,
        (organization["id"], agent_lookup),
    )
    if (
        not org_user
        or not org_user["is_active"]
        or not org_user["user_is_active"]
        or not verify_pin(agent_pin, org_user["agent_pin_hash"])
    ):
        _log_attempt(
            conn,
            organization_lookup=company_lookup,
            agent_lookup=agent_lookup,
            success=False,
            failure_reason="invalid_credentials",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        conn.commit()
        return AuthResult(False, "login.invalid_credentials")

    user = fetch_one(conn, "SELECT * FROM users WHERE id = ?", (org_user["user_id"],))
    _log_attempt(
        conn,
        organization_lookup=company_lookup,
        agent_lookup=agent_lookup,
        success=True,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    conn.commit()
    return AuthResult(True, "login.identified", organization=organization, user=user, org_user=org_user)


def password_mode(user: sqlite3.Row) -> str:
    if not user["password_hash"]:
        return "setup"
    if user["must_change_password"]:
        return "change"
    return "login"


def verify_user_password(user: sqlite3.Row, password: str) -> bool:
    return verify_password(password, user["password_hash"])


def set_user_password(conn: sqlite3.Connection, user_id: str, password: str, *, must_change: bool = False) -> None:
    now = utcnow_iso()
    update_by_id(
        conn,
        "users",
        user_id,
        {
            "password_hash": hash_password(password),
            "password_set_at": now,
            "must_change_password": 1 if must_change else 0,
            "updated_at": now,
        },
    )
    conn.commit()


def build_session_payload(organization: sqlite3.Row, user: sqlite3.Row, org_user: sqlite3.Row) -> dict[str, object]:
    return {
        "organization_id": organization["id"],
        "organization_name": organization["display_name"] or organization["name"],
        "organization_slug": organization["slug"],
        "user_id": user["id"],
        "display_name": user["display_name"],
        "org_user_id": org_user["id"],
        "role": org_user["role"],
        "can_view_team": bool(org_user["can_view_team"]),
        "language": user["preferred_language"] or organization["default_language"] or "fr",
    }
