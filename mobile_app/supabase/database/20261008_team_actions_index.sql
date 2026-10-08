-- Read-only team activity uses status, completion time and ID for stable
-- offset pagination. Run separately in Supabase SQL Editor (no transaction).
-- CONCURRENTLY keeps normal action writes available while the index builds.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_actions_team_completed
ON public.actions (organization_id, completed_at DESC, id DESC)
WHERE status = 'done' AND completed_at IS NOT NULL;
