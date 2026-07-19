-- NexStep uses a trusted server-side PostgreSQL connection from Streamlit.
-- Browser clients do not need direct Supabase Data API access. Enabling RLS
-- without public policies therefore blocks every anon/authenticated request,
-- while the private PostgreSQL owner connection used by Streamlit still works.

BEGIN;

ALTER TABLE public.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.organization_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lead_statuses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.client_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.action_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.touchpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transfers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.import_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.auth_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Remove the grants inherited by tables created outside Supabase Table Editor.
-- No permissive RLS policy is created because NexStep never queries these
-- tables with a browser-facing anon or authenticated API key.
REVOKE ALL PRIVILEGES ON TABLE
    public.organizations,
    public.users,
    public.organization_users,
    public.pipeline_stages,
    public.lead_statuses,
    public.client_categories,
    public.action_types,
    public.leads,
    public.contacts,
    public.actions,
    public.touchpoints,
    public.transfers,
    public.comments,
    public.import_batches,
    public.import_rows,
    public.auth_attempts,
    public.audit_logs
FROM anon, authenticated;

-- Tables created later by the postgres owner also start without public grants.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated;

COMMIT;
