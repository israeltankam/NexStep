"""Small, authorized pages of completed actions for one company team."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from database.repository import fetch_all, fetch_one


PAGE_SIZE = 20
TEAM_ROLES = frozenset({"manager", "company_admin"})


@dataclass(frozen=True)
class TeamActionPage:
    actions: list[dict[str, object]]
    offset: int
    has_more: bool


def list_team_actions(conn: sqlite3.Connection, *, organization_id: str,
                      actor_org_user_id: str, offset: int = 0) -> TeamActionPage:
    """Read at most one page plus a lookahead row; never count or load history.

    The permission check uses the current database role, rather than a possibly
    stale browser session. Every joined row is scoped to the actor's company.
    """
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        raise ValueError("invalid_offset")
    actor = fetch_one(conn, """
        SELECT ou.role FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        JOIN organizations o ON o.id = ou.organization_id
        WHERE ou.id = ? AND ou.organization_id = ?
          AND ou.is_active = 1 AND u.is_active = 1 AND o.is_active = 1
    """, (actor_org_user_id, organization_id))
    if not actor or actor["role"] not in TEAM_ROLES:
        raise PermissionError("forbidden")
    rows = fetch_all(conn, """
        SELECT a.id, a.title, a.completed_at, a.completion_note,
               l.id AS lead_id, l.name AS lead_name,
               u.display_name AS completed_by_name
        FROM actions a
        JOIN leads l ON l.id = a.lead_id AND l.organization_id = a.organization_id
        LEFT JOIN organization_users performer
          ON performer.id = a.completed_by_org_user_id
         AND performer.organization_id = a.organization_id
        LEFT JOIN users u ON u.id = performer.user_id
        WHERE a.organization_id = ? AND a.status = 'done'
          AND a.completed_at IS NOT NULL
        ORDER BY a.completed_at DESC, a.id DESC
        LIMIT ? OFFSET ?
    """, (organization_id, PAGE_SIZE + 1, offset))
    return TeamActionPage(actions=[dict(row) for row in rows[:PAGE_SIZE]],
                          offset=offset, has_more=len(rows) > PAGE_SIZE)
