"""Action workflow: next action, completion, follow-up, and transfer."""

from __future__ import annotations

import sqlite3

from database.connection import transaction
from database.repository import fetch_all, fetch_one, insert, update_by_id
from services.comment_service import add_comment, latest_comment_for_lead
from utils.dates import today, utcnow_iso
from utils.security import pin_lookup, verify_pin
from utils.text import new_id
from utils.urgency import urgency_color, urgency_rank


ACTION_SELECT = """
SELECT a.*, l.name AS lead_name, l.score, l.context_full, l.obstacle,
       ps.name AS stage_name, ls.name AS status_name, cc.name AS category_name,
       at.name AS action_type_name,
       c.full_name AS contact_name, c.phone_raw, c.channel_notes
FROM actions a
JOIN leads l ON l.id = a.lead_id
LEFT JOIN pipeline_stages ps ON ps.id = l.stage_id
LEFT JOIN lead_statuses ls ON ls.id = l.status_id
LEFT JOIN client_categories cc ON cc.id = l.category_id
LEFT JOIN action_types at ON at.id = a.action_type_id
LEFT JOIN contacts c ON c.lead_id = l.id AND c.is_primary = 1
"""


def get_next_action(conn: sqlite3.Connection, organization_id: str, org_user_id: str) -> sqlite3.Row | None:
    return fetch_one(
        conn,
        ACTION_SELECT
        + """
        WHERE a.organization_id = ?
          AND a.assigned_to_org_user_id = ?
          AND a.status = 'pending'
        ORDER BY
          CASE WHEN a.due_date IS NULL THEN 1 ELSE 0 END ASC,
          a.due_date ASC,
          l.score DESC,
          a.created_at ASC
        LIMIT 1
        """,
        (organization_id, org_user_id),
    )


def get_action_detail(conn: sqlite3.Connection, action_id: str) -> sqlite3.Row | None:
    return fetch_one(conn, ACTION_SELECT + " WHERE a.id = ?", (action_id,))


def list_actions(
    conn: sqlite3.Connection,
    organization_id: str,
    *,
    org_user_id: str | None = None,
    include_done: bool = False,
) -> list[dict[str, object]]:
    params: list[object] = [organization_id]
    clauses = ["a.organization_id = ?"]
    if org_user_id:
        clauses.append("a.assigned_to_org_user_id = ?")
        params.append(org_user_id)
    if not include_done:
        clauses.append("a.status = 'pending'")
    rows = fetch_all(
        conn,
        ACTION_SELECT
        + f"""
        WHERE {' AND '.join(clauses)}
        ORDER BY a.due_date ASC, l.score DESC, a.created_at ASC
        """,
        tuple(params),
    )
    decorated = []
    for row in rows:
        as_dict = dict(row)
        as_dict["urgency_color"] = urgency_color(row["due_date"])
        as_dict["urgency_rank"] = urgency_rank(row["due_date"])
        latest = latest_comment_for_lead(conn, row["lead_id"])
        as_dict["latest_comment"] = latest["body"] if latest else ""
        as_dict["latest_comment_type"] = latest["comment_type"] if latest else ""
        decorated.append(as_dict)
    return sorted(decorated, key=lambda item: (item["urgency_rank"], item["due_date"] or "9999-99-99", -(item["score"] or 0)))


def resolve_org_user_by_pin(conn: sqlite3.Connection, organization_id: str, agent_pin: str) -> sqlite3.Row | None:
    lookup = pin_lookup(agent_pin)
    row = fetch_one(
        conn,
        """
        SELECT ou.*, u.display_name
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.organization_id = ?
          AND ou.agent_pin_lookup = ?
          AND ou.is_active = 1
          AND u.is_active = 1
        """,
        (organization_id, lookup),
    )
    if row and verify_pin(agent_pin, row["agent_pin_hash"]):
        return row
    return None


def find_action_type_id(conn: sqlite3.Connection, organization_id: str, name: str | None) -> str | None:
    if not name:
        return None
    row = fetch_one(
        conn,
        "SELECT id FROM action_types WHERE organization_id = ? AND name = ?",
        (organization_id, name),
    )
    return row["id"] if row else None


def complete_action(
    conn: sqlite3.Connection,
    *,
    action_id: str,
    actor_org_user_id: str,
    completion_status: str,
    touchpoint_type: str,
    outcome: str,
    note: str,
    contact_name: str = "",
    obstacle: str = "",
    decision: str = "",
    create_next: bool = False,
    next_due_date: str | None = None,
    next_action_type: str | None = None,
    next_title: str | None = None,
    next_comment: str | None = None,
    next_assigned_org_user_id: str | None = None,
) -> dict[str, str | None]:
    """Close an action and optionally create the next one in the same transaction."""

    action = get_action_detail(conn, action_id)
    if not action:
        raise ValueError("Action not found.")
    if action["status"] != "pending":
        raise ValueError("Only pending actions can be completed.")

    with transaction(conn):
        now = utcnow_iso()
        touchpoint_id = new_id()
        insert(
            conn,
            "touchpoints",
            {
                "id": touchpoint_id,
                "organization_id": action["organization_id"],
                "lead_id": action["lead_id"],
                "action_id": action_id,
                "org_user_id": actor_org_user_id,
                "contact_id": None,
                "occurred_at": now,
                "touchpoint_type": touchpoint_type,
                "channel": action["channel_notes"],
                "outcome": outcome,
                "note": note.strip() or None,
                "decision_note": decision.strip() or None,
                "action_note": completion_status,
                "followup_note": next_comment.strip() if next_comment else None,
                "next_due_date": next_due_date,
                "source": "manual",
                "source_detail": "complete_action",
                "legacy_update_at": None,
                "created_at": now,
            },
        )
        update_by_id(
            conn,
            "actions",
            action_id,
            {
                "status": "done",
                "completed_at": now,
                "completed_by_org_user_id": actor_org_user_id,
                "completion_note": note.strip() or None,
                "updated_at": now,
            },
        )
        if obstacle.strip():
            update_by_id(conn, "leads", action["lead_id"], {"obstacle": obstacle.strip(), "updated_at": now})
        if contact_name.strip() and not action["contact_name"]:
            insert(
                conn,
                "contacts",
                {
                    "id": new_id(),
                    "lead_id": action["lead_id"],
                    "full_name": contact_name.strip(),
                    "role_title": None,
                    "phone_raw": None,
                    "phone_normalized": None,
                    "email": None,
                    "whatsapp": None,
                    "channel_notes": None,
                    "is_primary": 1,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        if note.strip():
            add_comment(
                conn,
                organization_id=action["organization_id"],
                lead_id=action["lead_id"],
                action_id=action_id,
                touchpoint_id=touchpoint_id,
                org_user_id=actor_org_user_id,
                body=note,
                comment_type="action_note",
                source="manual",
            )

        next_action_id = None
        if create_next:
            next_action_id = new_id()
            assigned_to = next_assigned_org_user_id or action["assigned_to_org_user_id"]
            insert(
                conn,
                "actions",
                {
                    "id": next_action_id,
                    "organization_id": action["organization_id"],
                    "lead_id": action["lead_id"],
                    "assigned_to_org_user_id": assigned_to,
                    "created_by_org_user_id": actor_org_user_id,
                    "action_type_id": find_action_type_id(conn, action["organization_id"], next_action_type),
                    "title": next_title.strip() if next_title else (next_action_type or "Prochaine action"),
                    "details": next_comment.strip() if next_comment else None,
                    "due_date": next_due_date,
                    "status": "pending",
                    "urgency_color_cache": urgency_color(next_due_date),
                    "completed_at": None,
                    "completed_by_org_user_id": None,
                    "completion_note": None,
                    "transferred_to_org_user_id": None,
                    "previous_action_id": action_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            update_by_id(conn, "leads", action["lead_id"], {"owner_org_user_id": assigned_to, "updated_at": now})
            if next_comment and next_comment.strip():
                add_comment(
                    conn,
                    organization_id=action["organization_id"],
                    lead_id=action["lead_id"],
                    action_id=next_action_id,
                    touchpoint_id=touchpoint_id,
                    org_user_id=actor_org_user_id,
                    body=next_comment,
                    comment_type="next_action_note",
                    source="manual",
                )
    return {"touchpoint_id": touchpoint_id, "next_action_id": next_action_id}


def transfer_action(
    conn: sqlite3.Connection,
    *,
    action_id: str,
    actor_org_user_id: str,
    target_agent_pin: str,
    transfer_note: str,
) -> dict[str, str]:
    action = get_action_detail(conn, action_id)
    if not action:
        raise ValueError("Action not found.")
    target = resolve_org_user_by_pin(conn, action["organization_id"], target_agent_pin)
    if not target:
        raise ValueError("Target agent not found.")

    with transaction(conn):
        now = utcnow_iso()
        transfer_id = new_id()
        insert(
            conn,
            "transfers",
            {
                "id": transfer_id,
                "organization_id": action["organization_id"],
                "lead_id": action["lead_id"],
                "action_id": action_id,
                "from_org_user_id": actor_org_user_id,
                "to_org_user_id": target["id"],
                "transfer_note": transfer_note.strip() or None,
                "created_at": now,
            },
        )
        update_by_id(
            conn,
            "actions",
            action_id,
            {
                "status": "transferred",
                "transferred_to_org_user_id": target["id"],
                "updated_at": now,
            },
        )
        new_action_id = new_id()
        insert(
            conn,
            "actions",
            {
                "id": new_action_id,
                "organization_id": action["organization_id"],
                "lead_id": action["lead_id"],
                "assigned_to_org_user_id": target["id"],
                "created_by_org_user_id": actor_org_user_id,
                "action_type_id": action["action_type_id"],
                "title": action["title"],
                "details": transfer_note.strip() or action["details"],
                "due_date": today().isoformat(),
                "status": "pending",
                "urgency_color_cache": urgency_color(today().isoformat()),
                "completed_at": None,
                "completed_by_org_user_id": None,
                "completion_note": None,
                "transferred_to_org_user_id": None,
                "previous_action_id": action_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        update_by_id(conn, "leads", action["lead_id"], {"owner_org_user_id": target["id"], "updated_at": now})
        if transfer_note.strip():
            add_comment(
                conn,
                organization_id=action["organization_id"],
                lead_id=action["lead_id"],
                action_id=action_id,
                transfer_id=transfer_id,
                org_user_id=actor_org_user_id,
                body=transfer_note,
                comment_type="transfer_note",
                source="manual",
            )
    return {"transfer_id": transfer_id, "new_action_id": new_action_id, "target_name": target["display_name"]}
