"""Database schema matching the NexStep MVP specification and its comment patch."""

from __future__ import annotations

import sqlite3


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS organizations (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        slug TEXT NOT NULL UNIQUE,
        display_name TEXT,
        company_pin_lookup TEXT NOT NULL UNIQUE,
        company_pin_hash TEXT NOT NULL,
        default_language TEXT NOT NULL DEFAULT 'fr',
        client_label TEXT NOT NULL DEFAULT 'Client',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        display_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        password_hash TEXT,
        password_set_at TEXT,
        must_change_password INTEGER NOT NULL DEFAULT 0,
        preferred_language TEXT NOT NULL DEFAULT 'fr',
        is_active INTEGER NOT NULL DEFAULT 1,
        is_global_admin INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS organization_users (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        agent_pin_lookup TEXT NOT NULL,
        agent_pin_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'agent',
        can_view_team INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        UNIQUE (organization_id, agent_pin_lookup),
        UNIQUE (organization_id, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pipeline_stages (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        is_won INTEGER NOT NULL DEFAULT 0,
        is_lost INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        UNIQUE (organization_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lead_statuses (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        color_name TEXT,
        position INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        UNIQUE (organization_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS client_categories (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        UNIQUE (organization_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS action_types (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        UNIQUE (organization_id, name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        owner_org_user_id TEXT,
        stage_id TEXT,
        status_id TEXT,
        category_id TEXT,
        city TEXT,
        address TEXT,
        latitude REAL,
        longitude REAL,
        score REAL,
        source TEXT,
        source_detail TEXT,
        obstacle TEXT,
        context_full TEXT,
        prioritization_reason TEXT,
        churn_flag INTEGER NOT NULL DEFAULT 0,
        legacy_rank REAL,
        legacy_row_number INTEGER,
        legacy_age_days INTEGER,
        legacy_touchpoint_count INTEGER,
        legacy_fields_json TEXT,
        possible_duplicate_group TEXT,
        is_archived INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (owner_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (stage_id) REFERENCES pipeline_stages(id),
        FOREIGN KEY (status_id) REFERENCES lead_statuses(id),
        FOREIGN KEY (category_id) REFERENCES client_categories(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS contacts (
        id TEXT PRIMARY KEY,
        lead_id TEXT NOT NULL,
        full_name TEXT,
        role_title TEXT,
        phone_raw TEXT,
        phone_normalized TEXT,
        email TEXT,
        whatsapp TEXT,
        channel_notes TEXT,
        is_primary INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actions (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        lead_id TEXT NOT NULL,
        assigned_to_org_user_id TEXT,
        created_by_org_user_id TEXT,
        action_type_id TEXT,
        title TEXT NOT NULL,
        details TEXT,
        due_date TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        urgency_color_cache TEXT,
        completed_at TEXT,
        completed_by_org_user_id TEXT,
        completion_note TEXT,
        transferred_to_org_user_id TEXT,
        previous_action_id TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (lead_id) REFERENCES leads(id),
        FOREIGN KEY (assigned_to_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (created_by_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (completed_by_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (transferred_to_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (action_type_id) REFERENCES action_types(id),
        FOREIGN KEY (previous_action_id) REFERENCES actions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS touchpoints (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        lead_id TEXT NOT NULL,
        action_id TEXT,
        org_user_id TEXT,
        contact_id TEXT,
        occurred_at TEXT NOT NULL,
        touchpoint_type TEXT,
        channel TEXT,
        outcome TEXT,
        note TEXT,
        decision_note TEXT,
        action_note TEXT,
        followup_note TEXT,
        next_due_date TEXT,
        source TEXT,
        source_detail TEXT,
        legacy_update_at TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (lead_id) REFERENCES leads(id),
        FOREIGN KEY (action_id) REFERENCES actions(id),
        FOREIGN KEY (org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (contact_id) REFERENCES contacts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transfers (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        lead_id TEXT NOT NULL,
        action_id TEXT,
        from_org_user_id TEXT,
        to_org_user_id TEXT NOT NULL,
        transfer_note TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (lead_id) REFERENCES leads(id),
        FOREIGN KEY (action_id) REFERENCES actions(id),
        FOREIGN KEY (from_org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (to_org_user_id) REFERENCES organization_users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS comments (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        lead_id TEXT NOT NULL,
        action_id TEXT,
        touchpoint_id TEXT,
        transfer_id TEXT,
        org_user_id TEXT,
        body TEXT NOT NULL,
        comment_type TEXT NOT NULL DEFAULT 'general',
        visibility TEXT NOT NULL DEFAULT 'team',
        source TEXT NOT NULL DEFAULT 'manual',
        source_column TEXT,
        is_pinned INTEGER NOT NULL DEFAULT 0,
        is_system_import INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (lead_id) REFERENCES leads(id),
        FOREIGN KEY (action_id) REFERENCES actions(id),
        FOREIGN KEY (touchpoint_id) REFERENCES touchpoints(id),
        FOREIGN KEY (transfer_id) REFERENCES transfers(id),
        FOREIGN KEY (org_user_id) REFERENCES organization_users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_batches (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        source_filename TEXT NOT NULL,
        imported_by_user_id TEXT,
        row_count INTEGER NOT NULL DEFAULT 0,
        imported_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'completed',
        notes TEXT,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (imported_by_user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS import_rows (
        id TEXT PRIMARY KEY,
        import_batch_id TEXT NOT NULL,
        lead_id TEXT,
        excel_sheet TEXT NOT NULL,
        excel_row_number INTEGER NOT NULL,
        raw_json TEXT NOT NULL,
        import_status TEXT NOT NULL DEFAULT 'imported',
        error_message TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (import_batch_id) REFERENCES import_batches(id),
        FOREIGN KEY (lead_id) REFERENCES leads(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_attempts (
        id TEXT PRIMARY KEY,
        organization_lookup TEXT,
        agent_lookup TEXT,
        success INTEGER NOT NULL,
        failure_reason TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        organization_id TEXT,
        actor_user_id TEXT,
        actor_org_user_id TEXT,
        entity_type TEXT NOT NULL,
        entity_id TEXT,
        action TEXT NOT NULL,
        before_json TEXT,
        after_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (actor_user_id) REFERENCES users(id),
        FOREIGN KEY (actor_org_user_id) REFERENCES organization_users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        org_user_id TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_used_at TEXT,
        revoked_at TEXT,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (org_user_id) REFERENCES organization_users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS password_reset_requests (
        id TEXT PRIMARY KEY,
        organization_id TEXT NOT NULL,
        user_id TEXT NOT NULL,
        org_user_id TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        requested_at TEXT NOT NULL,
        reviewed_at TEXT,
        reviewed_by_user_id TEXT,
        FOREIGN KEY (organization_id) REFERENCES organizations(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (org_user_id) REFERENCES organization_users(id),
        FOREIGN KEY (reviewed_by_user_id) REFERENCES users(id)
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_leads_org_owner ON leads(organization_id, owner_org_user_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_org_status ON leads(organization_id, status_id)",
    "CREATE INDEX IF NOT EXISTS idx_leads_org_stage ON leads(organization_id, stage_id)",
    "CREATE INDEX IF NOT EXISTS idx_actions_org_user_status_due ON actions(organization_id, assigned_to_org_user_id, status, due_date)",
    "CREATE INDEX IF NOT EXISTS idx_actions_org_lead ON actions(organization_id, lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_touchpoints_lead_date ON touchpoints(lead_id, occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_contacts_lead ON contacts(lead_id)",
    "CREATE INDEX IF NOT EXISTS idx_import_rows_batch ON import_rows(import_batch_id)",
    "CREATE INDEX IF NOT EXISTS idx_comments_lead_created ON comments(lead_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_comments_body ON comments(body)",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_token ON auth_sessions(token_hash)",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active ON auth_sessions(org_user_id, revoked_at, expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_password_resets_org_status ON password_reset_requests(organization_id, status, requested_at)",
    "CREATE INDEX IF NOT EXISTS idx_password_resets_user_status ON password_reset_requests(user_id, status)",
]


def create_schema(conn: sqlite3.Connection) -> None:
    for statement in SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in INDEX_STATEMENTS:
        conn.execute(statement)
    conn.commit()
