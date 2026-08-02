"""In-app password-reset requests reviewed by a company administrator."""

from __future__ import annotations

import sqlite3

from database.connection import transaction
from database.repository import fetch_all, fetch_one, insert, update_by_id
from services.access_service import revoke_all_user_access
from utils.dates import utcnow_iso
from utils.text import new_id


ADMIN_ROLES = {"company_admin", "super_admin"}


def _is_global_administrator(conn: sqlite3.Connection, user_id: str) -> bool:
    """Read the global flag from the database instead of trusting UI state."""

    user = fetch_one(
        conn,
        "SELECT is_global_admin FROM users WHERE id = ? AND is_active = 1",
        (user_id,),
    )
    return bool(user and user["is_global_admin"])


def _can_review_organization(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    organization_id: str,
) -> bool:
    """Allow active company administrators only inside their organization."""

    link = fetch_one(
        conn,
        """
        SELECT role
        FROM organization_users
        WHERE user_id = ? AND organization_id = ? AND is_active = 1
        """,
        (user_id, organization_id),
    )
    return bool(link and str(link["role"]) in ADMIN_ROLES)


def request_password_reset(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    user_id: str,
    org_user_id: str,
) -> str:
    """Create one pending request, reusing an existing pending request."""

    existing = fetch_one(
        conn,
        """
        SELECT id
        FROM password_reset_requests
        WHERE organization_id = ? AND user_id = ? AND status = 'pending'
        ORDER BY requested_at DESC
        LIMIT 1
        """,
        (organization_id, user_id),
    )
    if existing:
        return str(existing["id"])

    request_id = new_id()
    insert(
        conn,
        "password_reset_requests",
        {
            "id": request_id,
            "organization_id": organization_id,
            "user_id": user_id,
            "org_user_id": org_user_id,
            "status": "pending",
            "requested_at": utcnow_iso(),
            "reviewed_at": None,
            "reviewed_by_user_id": None,
        },
    )
    conn.commit()
    return request_id


def list_pending_requests(
    conn: sqlite3.Connection,
    organization_id: str,
    *,
    reviewer_user_id: str,
) -> list[dict[str, object]]:
    """List the reviewer's company inbox, or every inbox for a global admin."""

    global_scope = _is_global_administrator(conn, reviewer_user_id)
    if not global_scope and not _can_review_organization(
        conn,
        user_id=reviewer_user_id,
        organization_id=organization_id,
    ):
        raise PermissionError("password_reset_review_forbidden")

    scope_clause = "" if global_scope else "AND pr.organization_id = ?"
    parameters = () if global_scope else (organization_id,)
    rows = fetch_all(
        conn,
        f"""
        SELECT pr.*, u.display_name, u.email,
               COALESCE(o.display_name, o.name) AS organization_name
        FROM password_reset_requests pr
        JOIN users u ON u.id = pr.user_id
        JOIN organizations o ON o.id = pr.organization_id
        WHERE pr.status = 'pending' {scope_clause}
        ORDER BY pr.requested_at ASC
        """,
        parameters,
    )
    return [dict(row) for row in rows]


def review_password_reset(
    conn: sqlite3.Connection,
    *,
    request_id: str,
    organization_id: str,
    reviewer_user_id: str,
    approve: bool,
) -> bool:
    """Approve or reject a pending request without exposing credentials."""

    request_row = fetch_one(
        conn,
        """
        SELECT *
        FROM password_reset_requests
        WHERE id = ? AND status = 'pending'
        """,
        (request_id,),
    )
    if not request_row:
        return False

    request_organization_id = str(request_row["organization_id"])
    global_scope = _is_global_administrator(conn, reviewer_user_id)
    if not global_scope and (
        request_organization_id != organization_id
        or not _can_review_organization(
            conn,
            user_id=reviewer_user_id,
            organization_id=request_organization_id,
        )
    ):
        return False

    now = utcnow_iso()
    with transaction(conn):
        if approve:
            # A null hash intentionally returns the user to first-password setup.
            conn.execute(
                """
                UPDATE users
                SET password_hash = NULL, password_set_at = NULL,
                    must_change_password = 0, updated_at = ?
                WHERE id = ?
                """,
                (now, request_row["user_id"]),
            )
            revoke_all_user_access(conn, str(request_row["user_id"]))
        update_by_id(
            conn,
            "password_reset_requests",
            request_id,
            {
                "status": "approved" if approve else "rejected",
                "reviewed_at": now,
                "reviewed_by_user_id": reviewer_user_id,
            },
        )
        insert(
            conn,
            "audit_logs",
            {
                "id": new_id(),
                "organization_id": request_organization_id,
                "actor_user_id": reviewer_user_id,
                "actor_org_user_id": None,
                "entity_type": "password_reset_request",
                "entity_id": request_id,
                "action": "approve" if approve else "reject",
                "before_json": '{"status":"pending"}',
                "after_json": '{"status":"approved"}' if approve else '{"status":"rejected"}',
                "created_at": now,
            },
        )
    return True
