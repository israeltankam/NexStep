"""In-app password-reset requests reviewed by a company administrator."""

from __future__ import annotations

import sqlite3

from database.connection import transaction
from database.repository import fetch_all, fetch_one, insert, update_by_id
from services.access_service import revoke_all_user_access
from utils.dates import utcnow_iso
from utils.text import new_id


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
) -> list[dict[str, object]]:
    rows = fetch_all(
        conn,
        """
        SELECT pr.*, u.display_name, u.email
        FROM password_reset_requests pr
        JOIN users u ON u.id = pr.user_id
        WHERE pr.organization_id = ? AND pr.status = 'pending'
        ORDER BY pr.requested_at ASC
        """,
        (organization_id,),
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
        WHERE id = ? AND organization_id = ? AND status = 'pending'
        """,
        (request_id, organization_id),
    )
    if not request_row:
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
                "organization_id": organization_id,
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
