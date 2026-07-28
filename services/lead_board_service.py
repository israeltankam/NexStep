"""Aggregated, user-facing data for the NexStep Lead Board."""

from __future__ import annotations

import io
import sqlite3
from collections import defaultdict
from collections.abc import Iterable

import pandas as pd

from database.repository import fetch_all, fetch_one
from utils.dates import format_date
from utils.urgency import urgency_color, urgency_label, urgency_rank


def list_team_members(conn: sqlite3.Connection, organization_id: str) -> list[dict[str, object]]:
    """Return every active member, including members with no assigned lead."""

    rows = fetch_all(
        conn,
        """
        SELECT ou.id AS org_user_id, ou.role, ou.can_view_team,
               u.display_name, u.email, u.phone
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.organization_id = ?
          AND ou.is_active = 1
          AND u.is_active = 1
        ORDER BY u.display_name ASC
        """,
        (organization_id,),
    )
    return [dict(row) for row in rows]


def _rows_for_ids(
    conn: sqlite3.Connection,
    query_prefix: str,
    lead_ids: list[str],
    *,
    suffix: str = "",
) -> list[sqlite3.Row]:
    """Run a trusted bulk query without one database round trip per lead."""

    if not lead_ids:
        return []
    placeholders = ", ".join("?" for _ in lead_ids)
    return fetch_all(conn, f"{query_prefix} ({placeholders}) {suffix}", tuple(lead_ids))


def build_lead_board(
    conn: sqlite3.Connection,
    organization_id: str,
    *,
    allowed_owner_ids: Iterable[str] | None = None,
) -> list[dict[str, object]]:
    """Build one readable board row per non-archived prospect."""

    params: list[object] = [organization_id]
    owner_clause = ""
    owner_ids = list(dict.fromkeys(str(value) for value in (allowed_owner_ids or []) if value))
    if allowed_owner_ids is not None:
        if not owner_ids:
            return []
        owner_clause = f"AND l.owner_org_user_id IN ({', '.join('?' for _ in owner_ids)})"
        params.extend(owner_ids)

    leads = fetch_all(
        conn,
        f"""
        SELECT l.id, l.name, l.owner_org_user_id, l.city, l.address, l.score,
               l.source, l.obstacle, l.context_full, l.created_at,
               ps.name AS stage_name, ls.name AS status_name,
               cc.name AS category_name, u.display_name AS owner_name
        FROM leads l
        LEFT JOIN pipeline_stages ps ON ps.id = l.stage_id
        LEFT JOIN lead_statuses ls ON ls.id = l.status_id
        LEFT JOIN client_categories cc ON cc.id = l.category_id
        LEFT JOIN organization_users ou ON ou.id = l.owner_org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE l.organization_id = ?
          AND l.is_archived = 0
          {owner_clause}
        ORDER BY l.name ASC
        """,
        tuple(params),
    )
    lead_ids = [str(row["id"]) for row in leads]

    contacts_by_lead: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _rows_for_ids(
        conn,
        "SELECT * FROM contacts WHERE lead_id IN",
        lead_ids,
        suffix="ORDER BY is_primary DESC, created_at ASC",
    ):
        contacts_by_lead[str(row["lead_id"])].append(dict(row))

    actions_by_lead: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _rows_for_ids(
        conn,
        """
        SELECT a.*, at.name AS action_type_name
        FROM actions a
        LEFT JOIN action_types at ON at.id = a.action_type_id
        WHERE a.lead_id IN
        """,
        lead_ids,
        suffix="ORDER BY a.created_at DESC",
    ):
        actions_by_lead[str(row["lead_id"])].append(dict(row))

    comments_by_lead: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _rows_for_ids(
        conn,
        """
        SELECT c.*, u.display_name AS author_name
        FROM comments c
        LEFT JOIN organization_users ou ON ou.id = c.org_user_id
        LEFT JOIN users u ON u.id = ou.user_id
        WHERE c.lead_id IN
        """,
        lead_ids,
        suffix="ORDER BY c.created_at DESC",
    ):
        comments_by_lead[str(row["lead_id"])].append(dict(row))

    board: list[dict[str, object]] = []
    for lead_row in leads:
        lead = dict(lead_row)
        lead_id = str(lead["id"])
        contacts = contacts_by_lead[lead_id]
        actions = actions_by_lead[lead_id]
        comments = comments_by_lead[lead_id]
        pending_actions = [action for action in actions if action["status"] == "pending"]
        pending_actions.sort(
            key=lambda action: (
                urgency_rank(action.get("due_date")),
                str(action.get("due_date") or "9999-12-31"),
                str(action.get("created_at") or ""),
            )
        )
        next_action = pending_actions[0] if pending_actions else None
        color = urgency_color(next_action.get("due_date") if next_action else None)

        contact_labels = []
        for contact in contacts:
            identity = str(contact.get("full_name") or "").strip()
            role = str(contact.get("role_title") or "").strip()
            phone = str(contact.get("phone_raw") or "").strip()
            label = identity
            if role:
                label = f"{label} ({role})" if label else role
            if phone:
                label = f"{label} - {phone}" if label else phone
            if label:
                contact_labels.append(label)

        board.append(
            {
                **lead,
                "contacts": contacts,
                "contacts_text": " | ".join(contact_labels),
                "actions": actions,
                "pending_action_count": len(pending_actions),
                "action_count": len(actions),
                "next_action": next_action,
                "next_action_title": next_action.get("title") if next_action else None,
                "next_due_date": next_action.get("due_date") if next_action else None,
                "urgency_color": color,
                "comments": comments,
                "comment_count": len(comments),
                "latest_comment": comments[0].get("body") if comments else None,
            }
        )
    return board


def filter_lead_board(
    rows: list[dict[str, object]],
    *,
    search: str = "",
    urgency_colors: set[str] | None = None,
    owner_ids: set[str] | None = None,
    stages: set[str] | None = None,
    statuses: set[str] | None = None,
) -> list[dict[str, object]]:
    """Apply the interactive filters without issuing another database query."""

    needle = search.strip().casefold()
    filtered = []
    for row in rows:
        searchable = " ".join(
            str(row.get(key) or "")
            for key in (
                "name",
                "contacts_text",
                "next_action_title",
                "latest_comment",
                "owner_name",
                "city",
                "category_name",
            )
        ).casefold()
        if needle and needle not in searchable:
            continue
        if urgency_colors is not None and row["urgency_color"] not in urgency_colors:
            continue
        if owner_ids is not None and row.get("owner_org_user_id") not in owner_ids:
            continue
        if stages is not None and (row.get("stage_name") or "") not in stages:
            continue
        if statuses is not None and (row.get("status_name") or "") not in statuses:
            continue
        filtered.append(row)
    return filtered


def team_board_summary(
    conn: sqlite3.Connection,
    organization_id: str,
    board_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize the full team while retaining zero-activity members."""

    members = list_team_members(conn, organization_id)
    by_owner: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in board_rows:
        if row.get("owner_org_user_id"):
            by_owner[str(row["owner_org_user_id"])].append(row)

    summary = []
    for member in members:
        rows = by_owner[str(member["org_user_id"])]
        summary.append(
            {
                **member,
                "lead_count": len(rows),
                "pending_action_count": sum(int(row["pending_action_count"]) for row in rows),
                "overdue_count": sum(1 for row in rows if row["urgency_color"] == "red"),
            }
        )
    return summary


def lead_board_excel(rows: list[dict[str, object]], language: str) -> bytes:
    """Create an Excel workbook containing only the currently filtered board."""

    translated = []
    for row in rows:
        translated.append(
            {
                "Prospect": row.get("name") or "",
                "Contacts": row.get("contacts_text") or "",
                "Prochaine action" if language == "fr" else "Next action": row.get("next_action_title") or "",
                "Echeance" if language == "fr" else "Due date": format_date(row.get("next_due_date"), ""),
                "Urgence" if language == "fr" else "Urgency": urgency_label(
                    str(row.get("urgency_color") or "gray"), language
                ),
                "Agent": row.get("owner_name") or "",
                "Dernier commentaire" if language == "fr" else "Latest comment": row.get("latest_comment") or "",
                "Etape" if language == "fr" else "Stage": row.get("stage_name") or "",
                "Statut" if language == "fr" else "Status": row.get("status_name") or "",
                "Ville" if language == "fr" else "City": row.get("city") or "",
            }
        )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame = pd.DataFrame(translated)
        frame.to_excel(writer, index=False, sheet_name="Lead Board")
        worksheet = writer.sheets["Lead Board"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
        for column_cells in worksheet.columns:
            width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 55)
            worksheet.column_dimensions[column_cells[0].column_letter].width = max(width, 12)
    return output.getvalue()


def get_board_lead(rows: list[dict[str, object]], lead_id: str | None) -> dict[str, object] | None:
    """Resolve a selected board row without another query."""

    if not lead_id:
        return None
    return next((row for row in rows if str(row["id"]) == str(lead_id)), None)


def organization_name(conn: sqlite3.Connection, organization_id: str) -> str:
    row = fetch_one(conn, "SELECT name, display_name FROM organizations WHERE id = ?", (organization_id,))
    return str((row["display_name"] or row["name"]) if row else "NexStep")
