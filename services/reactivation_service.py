"""Restart a stopped lead with a reason and a new pending action."""

from __future__ import annotations

from database.connection import transaction
from database.repository import fetch_one, insert, update_by_id
from services.audit_service import log_event
from services.comment_service import add_comment
from services.lead_permissions import editable_lead
from utils.dates import utcnow_iso
from utils.text import new_id
from utils.urgency import urgency_color


def reactivate_lead(conn, *, lead_id: str, actor_org_user_id: str,
                    reason: str, title: str, due_date: str | None,
                    action_type_id: str | None = None) -> str:
    """Require a stopped history and prevent duplicate active follow-ups."""
    lead = editable_lead(conn, lead_id, actor_org_user_id)
    reason, title = reason.strip(), title.strip()
    if not reason or len(reason) > 2000:
        raise ValueError("reason_required")
    if not title or len(title) > 200:
        raise ValueError("action_required")
    if fetch_one(conn, "SELECT id FROM actions WHERE lead_id = ? AND status = 'pending' LIMIT 1", (lead_id,)):
        raise ValueError("already_active")
    previous = fetch_one(conn, "SELECT id FROM actions WHERE lead_id = ? ORDER BY created_at DESC LIMIT 1", (lead_id,))
    if not previous and not lead["churn_flag"]:
        raise ValueError("not_stopped")
    if action_type_id and not fetch_one(conn, "SELECT id FROM action_types WHERE id = ? AND organization_id = ? AND is_active = 1", (action_type_id, lead["organization_id"])):
        raise ValueError("invalid_action_type")
    now, action_id = utcnow_iso(), new_id()
    with transaction(conn):
        insert(conn, "actions", {"id": action_id, "organization_id": lead["organization_id"],
            "lead_id": lead_id, "assigned_to_org_user_id": lead["owner_org_user_id"] or actor_org_user_id,
            "created_by_org_user_id": actor_org_user_id, "action_type_id": action_type_id,
            "title": title, "details": None, "due_date": due_date,
            "status": "pending", "urgency_color_cache": urgency_color(due_date),
            "previous_action_id": previous["id"] if previous else None,
            "created_at": now, "updated_at": now})
        update_by_id(conn, "leads", lead_id, {"churn_flag": 0, "updated_at": now})
        add_comment(conn, organization_id=lead["organization_id"], lead_id=lead_id,
                    action_id=action_id, org_user_id=actor_org_user_id,
                    body=reason, comment_type="reactivation_reason")
        log_event(conn, organization_id=lead["organization_id"],
                  actor_org_user_id=actor_org_user_id, entity_type="lead",
                  entity_id=lead_id, action="reactivate", after={"action_id": action_id})
    return action_id
