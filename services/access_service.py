"""Revocable quick-access files that never contain a PIN or password."""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3

from database.connection import transaction
from database.repository import fetch_one, insert, update_by_id
from utils.dates import utcnow_iso
from utils.text import new_id


ACCESS_FILE_VERSION = 1
DEFAULT_VALIDITY_DAYS = 30
MAX_FILE_BYTES = 16_384


@dataclasses.dataclass(frozen=True)
class QuickAccessResult:
    ok: bool
    message_key: str
    organization: sqlite3.Row | None = None
    user: sqlite3.Row | None = None
    org_user: sqlite3.Row | None = None
    session_id: str | None = None


def _token_hash(token: str) -> str:
    """Bind bearer tokens to the server-side pepper before storage."""

    pepper = os.getenv("APP_PIN_PEPPER", "nexstep-local-dev-pepper-change-me")
    return hmac.new(pepper.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def create_quick_access_file(
    conn: sqlite3.Connection,
    *,
    organization_id: str,
    user_id: str,
    org_user_id: str,
    validity_days: int = DEFAULT_VALIDITY_DAYS,
) -> tuple[str, bytes]:
    """Create a revocable session and return its portable JSON access file."""

    if validity_days < 1 or validity_days > 90:
        raise ValueError("invalid_validity")
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    token = secrets.token_urlsafe(32)
    session_id = new_id()
    expires_at = (now + dt.timedelta(days=validity_days)).isoformat()
    with transaction(conn):
        insert(
            conn,
            "auth_sessions",
            {
                "id": session_id,
                "organization_id": organization_id,
                "user_id": user_id,
                "org_user_id": org_user_id,
                "token_hash": _token_hash(token),
                "expires_at": expires_at,
                "created_at": now.isoformat(),
                "last_used_at": None,
                "revoked_at": None,
            },
        )
    payload = {
        "version": ACCESS_FILE_VERSION,
        "session_id": session_id,
        "token": token,
        "expires_at": expires_at,
    }
    return session_id, json.dumps(payload, indent=2).encode("utf-8")


def authenticate_quick_access(conn: sqlite3.Connection, file_content: bytes) -> QuickAccessResult:
    """Validate an access file and load the same rows used by PIN login."""

    if not file_content or len(file_content) > MAX_FILE_BYTES:
        return QuickAccessResult(False, "quick_access.invalid")
    try:
        payload = json.loads(file_content.decode("utf-8"))
        if payload.get("version") != ACCESS_FILE_VERSION:
            raise ValueError
        session_id = str(payload["session_id"])
        token = str(payload["token"])
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return QuickAccessResult(False, "quick_access.invalid")

    session_row = fetch_one(
        conn,
        """
        SELECT *
        FROM auth_sessions
        WHERE id = ?
          AND token_hash = ?
          AND revoked_at IS NULL
        """,
        (session_id, _token_hash(token)),
    )
    if not session_row:
        return QuickAccessResult(False, "quick_access.invalid")
    try:
        expires_at = dt.datetime.fromisoformat(str(session_row["expires_at"]))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=dt.UTC)
    except ValueError:
        return QuickAccessResult(False, "quick_access.invalid")
    if expires_at <= dt.datetime.now(dt.UTC):
        return QuickAccessResult(False, "quick_access.expired")

    organization = fetch_one(
        conn,
        "SELECT * FROM organizations WHERE id = ? AND is_active = 1",
        (session_row["organization_id"],),
    )
    user = fetch_one(
        conn,
        "SELECT * FROM users WHERE id = ? AND is_active = 1",
        (session_row["user_id"],),
    )
    org_user = fetch_one(
        conn,
        """
        SELECT *
        FROM organization_users
        WHERE id = ? AND organization_id = ? AND user_id = ? AND is_active = 1
        """,
        (session_row["org_user_id"], session_row["organization_id"], session_row["user_id"]),
    )
    if not organization or not user or not org_user:
        return QuickAccessResult(False, "quick_access.invalid")

    update_by_id(conn, "auth_sessions", session_id, {"last_used_at": utcnow_iso()})
    conn.commit()
    return QuickAccessResult(
        True,
        "quick_access.success",
        organization=organization,
        user=user,
        org_user=org_user,
        session_id=session_id,
    )


def revoke_quick_access(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    org_user_id: str,
) -> bool:
    """Revoke one current user's token without affecting their password login."""

    row = fetch_one(
        conn,
        "SELECT id FROM auth_sessions WHERE id = ? AND org_user_id = ? AND revoked_at IS NULL",
        (session_id, org_user_id),
    )
    if not row:
        return False
    update_by_id(conn, "auth_sessions", session_id, {"revoked_at": utcnow_iso()})
    conn.commit()
    return True


def revoke_all_user_access(conn: sqlite3.Connection, user_id: str) -> None:
    """Revoke every portable access token after a credential reset."""

    conn.execute(
        "UPDATE auth_sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (utcnow_iso(), user_id),
    )
