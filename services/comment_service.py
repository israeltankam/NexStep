"""Comment service, including the legacy Excel column `a` patch behavior."""

from __future__ import annotations

import sqlite3

from database.repository import fetch_all, fetch_one, insert
from utils.dates import utcnow_iso
from utils.text import new_id


def add_comment(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    lead_id: str,
    body: str,
    org_user_id: str | None = None,
    action_id: str | None = None,
    touchpoint_id: str | None = None,
    transfer_id: str | None = None,
    comment_type: str = "general",
    visibility: str = "team",
    source: str = "manual",
    source_column: str | None = None,
    is_pinned: bool = False,
    is_system_import: bool = False,
) -> str:
    """Create a comment without forcing an action to be completed."""

    cleaned = body.strip()
    if not cleaned:
        raise ValueError("Comment body cannot be empty.")
    comment_id = new_id()
    now = utcnow_iso()
    insert(
        conn,
        "comments",
        {
            "id": comment_id,
            "organization_id": organization_id,
            "lead_id": lead_id,
            "action_id": action_id,
            "touchpoint_id": touchpoint_id,
            "transfer_id": transfer_id,
            "org_user_id": org_user_id,
            "body": cleaned,
            "comment_type": comment_type,
            "visibility": visibility,
            "source": source,
            "source_column": source_column,
            "is_pinned": 1 if is_pinned else 0,
            "is_system_import": 1 if is_system_import else 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    return comment_id


def list_comments_for_lead(conn: sqlite3.Connection, lead_id: str) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        """
        SELECT c.*, u.display_name AS author_name
        FROM comments c
        LEFT JOIN organization_users ou ON ou.id = c.org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE c.lead_id = ?
        ORDER BY c.is_pinned DESC, c.created_at DESC
        """,
        (lead_id,),
    )


def recent_comments_for_lead(conn: sqlite3.Connection, lead_id: str, limit: int = 3) -> list[sqlite3.Row]:
    return fetch_all(
        conn,
        """
        SELECT c.*, u.display_name AS author_name
        FROM comments c
        LEFT JOIN organization_users ou ON ou.id = c.org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE c.lead_id = ?
        ORDER BY c.created_at DESC
        LIMIT ?
        """,
        (lead_id, limit),
    )


def latest_comment_for_lead(conn: sqlite3.Connection, lead_id: str) -> sqlite3.Row | None:
    return fetch_one(
        conn,
        """
        SELECT c.*, u.display_name AS author_name
        FROM comments c
        LEFT JOIN organization_users ou ON ou.id = c.org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE c.lead_id = ?
        ORDER BY c.created_at DESC
        LIMIT 1
        """,
        (lead_id,),
    )


def search_comments(conn: sqlite3.Connection, organization_id: str, query: str) -> list[sqlite3.Row]:
    like = f"%{query.strip()}%"
    if like == "%%":
        return []
    return fetch_all(
        conn,
        """
        SELECT c.*, l.name AS lead_name, u.display_name AS author_name
        FROM comments c
        JOIN leads l ON l.id = c.lead_id
        LEFT JOIN organization_users ou ON ou.id = c.org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE c.organization_id = ?
          AND (c.body LIKE ? OR l.name LIKE ?)
        ORDER BY c.created_at DESC
        LIMIT 50
        """,
        (organization_id, like, like),
    )


def comment_badge(comment: sqlite3.Row) -> str:
    if comment["comment_type"] == "legacy_excel_a":
        return "Import Excel · Ancien commentaire · Colonne a"
    if comment["comment_type"] == "transfer_note":
        return "Transfert"
    if comment["comment_type"] == "action_note":
        return "Action"
    if comment["comment_type"] == "next_action_note":
        return "Prochaine action"
    return "Commentaire"
