"""Audit helpers for business events that should remain traceable."""

from __future__ import annotations

import json
import sqlite3

from database.repository import insert
from utils.dates import utcnow_iso
from utils.text import new_id


def log_event(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    action: str,
    organization_id: str | None = None,
    actor_user_id: str | None = None,
    actor_org_user_id: str | None = None,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    insert(
        conn,
        "audit_logs",
        {
            "id": new_id(),
            "organization_id": organization_id,
            "actor_user_id": actor_user_id,
            "actor_org_user_id": actor_org_user_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action,
            "before_json": json.dumps(before, ensure_ascii=False) if before else None,
            "after_json": json.dumps(after, ensure_ascii=False) if after else None,
            "created_at": utcnow_iso(),
        },
    )
