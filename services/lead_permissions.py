"""Server-side lead permissions shared by editing and reactivation workflows."""

from __future__ import annotations

from database.repository import fetch_one


def editable_lead(conn, lead_id: str, actor_org_user_id: str):
    """Return a lead only when the active actor may change it.

    A global administrator may work across companies; a company administrator
    may work across owners within their company; agents need ownership.
    """
    actor = fetch_one(conn, """
        SELECT ou.organization_id, ou.role, u.is_global_admin
        FROM organization_users ou JOIN users u ON u.id = ou.user_id
        WHERE ou.id = ? AND ou.is_active = 1 AND u.is_active = 1
    """, (actor_org_user_id,))
    lead = fetch_one(conn, "SELECT * FROM leads WHERE id = ? AND is_archived = 0", (lead_id,))
    if not actor or not lead:
        raise PermissionError("forbidden")
    if actor["is_global_admin"]:
        return lead
    if lead["organization_id"] != actor["organization_id"]:
        raise PermissionError("forbidden")
    if actor["role"] in {"company_admin", "super_admin"}:
        return lead
    if lead["owner_org_user_id"] != actor_org_user_id:
        raise PermissionError("forbidden")
    return lead
