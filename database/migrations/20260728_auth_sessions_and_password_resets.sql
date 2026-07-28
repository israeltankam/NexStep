-- NexStep production migration - 2026-07-28
--
-- This migration is intentionally additive. It creates two isolated tables
-- and their indexes. It never updates, deletes, truncates, or replaces an
-- existing row.

BEGIN;

CREATE TABLE IF NOT EXISTS public.auth_sessions (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES public.organizations(id),
    user_id TEXT NOT NULL REFERENCES public.users(id),
    org_user_id TEXT NOT NULL REFERENCES public.organization_users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_auth_sessions_token
    ON public.auth_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_active
    ON public.auth_sessions(org_user_id, revoked_at, expires_at);

CREATE TABLE IF NOT EXISTS public.password_reset_requests (
    id TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL REFERENCES public.organizations(id),
    user_id TEXT NOT NULL REFERENCES public.users(id),
    org_user_id TEXT NOT NULL REFERENCES public.organization_users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    requested_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by_user_id TEXT REFERENCES public.users(id)
);

CREATE INDEX IF NOT EXISTS idx_password_resets_org_status
    ON public.password_reset_requests(organization_id, status, requested_at);
CREATE INDEX IF NOT EXISTS idx_password_resets_user_status
    ON public.password_reset_requests(user_id, status);

ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.password_reset_requests ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
    public.auth_sessions,
    public.password_reset_requests
FROM anon, authenticated;

COMMIT;
