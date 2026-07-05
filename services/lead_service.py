"""Lead and team-summary queries."""

from __future__ import annotations

import sqlite3

from database.repository import fetch_all, fetch_one
from services.comment_service import latest_comment_for_lead
from utils.urgency import urgency_color


def get_lead_detail(conn: sqlite3.Connection, lead_id: str) -> sqlite3.Row | None:
    return fetch_one(
        conn,
        """
        SELECT l.*, ps.name AS stage_name, ls.name AS status_name, cc.name AS category_name,
               u.display_name AS owner_name
        FROM leads l
        LEFT JOIN pipeline_stages ps ON ps.id = l.stage_id
        LEFT JOIN lead_statuses ls ON ls.id = l.status_id
        LEFT JOIN client_categories cc ON cc.id = l.category_id
        LEFT JOIN organization_users ou ON ou.id = l.owner_org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE l.id = ?
        """,
        (lead_id,),
    )


def get_primary_contact(conn: sqlite3.Connection, lead_id: str) -> sqlite3.Row | None:
    return fetch_one(
        conn,
        "SELECT * FROM contacts WHERE lead_id = ? ORDER BY is_primary DESC, created_at ASC LIMIT 1",
        (lead_id,),
    )


def list_leads(conn: sqlite3.Connection, organization_id: str, search: str = "") -> list[sqlite3.Row]:
    params: list[object] = [organization_id]
    clause = ""
    if search.strip():
        clause = "AND l.name LIKE ?"
        params.append(f"%{search.strip()}%")
    return fetch_all(
        conn,
        f"""
        SELECT l.*, ps.name AS stage_name, ls.name AS status_name, cc.name AS category_name,
               u.display_name AS owner_name
        FROM leads l
        LEFT JOIN pipeline_stages ps ON ps.id = l.stage_id
        LEFT JOIN lead_statuses ls ON ls.id = l.status_id
        LEFT JOIN client_categories cc ON cc.id = l.category_id
        LEFT JOIN organization_users ou ON ou.id = l.owner_org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE l.organization_id = ? {clause}
        ORDER BY l.name ASC
        LIMIT 100
        """,
        tuple(params),
    )


def list_reference_values(conn: sqlite3.Connection, organization_id: str, table: str) -> list[str]:
    allowed = {"pipeline_stages", "lead_statuses", "client_categories", "action_types"}
    if table not in allowed:
        raise ValueError("Unsupported reference table.")
    rows = fetch_all(
        conn,
        f"SELECT name FROM {table} WHERE organization_id = ? AND is_active = 1 ORDER BY position ASC, name ASC",
        (organization_id,),
    )
    return [row["name"] for row in rows]


def team_summary(conn: sqlite3.Connection, organization_id: str) -> list[dict[str, object]]:
    agents = fetch_all(
        conn,
        """
        SELECT ou.id AS org_user_id, u.display_name, ou.role
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.organization_id = ?
          AND ou.is_active = 1
          AND u.is_active = 1
          AND ou.role != 'super_admin'
        ORDER BY u.display_name ASC
        """,
        (organization_id,),
    )
    summaries: list[dict[str, object]] = []
    for agent in agents:
        actions = fetch_all(
            conn,
            """
            SELECT a.*, l.name AS lead_name
            FROM actions a
            JOIN leads l ON l.id = a.lead_id
            WHERE a.organization_id = ?
              AND a.assigned_to_org_user_id = ?
              AND a.status = 'pending'
            ORDER BY a.due_date ASC
            """,
            (organization_id, agent["org_user_id"]),
        )
        counts = {"red": 0, "yellow": 0, "green": 0, "blue": 0, "gray": 0}
        for action in actions:
            counts[urgency_color(action["due_date"])] += 1
        recent_comments = []
        for action in actions[:5]:
            comment = latest_comment_for_lead(conn, action["lead_id"])
            if comment:
                recent_comments.append(comment)
        summaries.append(
            {
                "agent": agent,
                "total_actions": len(actions),
                "urgencies": counts,
                "actions": actions,
                "recent_comments": recent_comments,
            }
        )
    return summaries


def unassigned_leads_count(conn: sqlite3.Connection, organization_id: str) -> int:
    row = fetch_one(
        conn,
        "SELECT COUNT(*) AS count FROM leads WHERE organization_id = ? AND owner_org_user_id IS NULL",
        (organization_id,),
    )
    return int(row["count"] if row else 0)
