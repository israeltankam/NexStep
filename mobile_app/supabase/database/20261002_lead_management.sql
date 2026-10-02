-- Additive NexStep lead management: run in Supabase SQL Editor before deploying
-- the updated Edge Function. Existing tables and data are preserved.
BEGIN;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_complete_action_v2(
    p_organization_id text,
    p_actor_org_user_id text,
    p_action_id text,
    p_outcome text,
    p_note text,
    p_contact_name text,
    p_contact_role text,
    p_contact_phone text,
    p_contact_email text,
    p_contact_whatsapp text,
    p_obstacle text,
    p_decision text,
    p_create_next boolean,
    p_next_due_date text,
    p_next_action_type_name text,
    p_next_title text,
    p_next_comment text,
    p_next_assigned_org_user_id text,
    p_touchpoint_id text,
    p_next_action_id text,
    p_contact_id text,
    p_comment_id text,
    p_next_comment_id text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
    v_action actions%ROWTYPE;
    v_role text;
    v_channel text;
    v_touchpoint_type text;
    v_next_type_id text;
    v_contact_id text;
BEGIN
    SELECT role INTO v_role
    FROM organization_users
    WHERE id = p_actor_org_user_id
      AND organization_id = p_organization_id
      AND is_active = 1;
    SELECT * INTO v_action
    FROM actions
    WHERE id = p_action_id AND organization_id = p_organization_id
    FOR UPDATE;
    IF v_action.id IS NULL OR v_role IS NULL THEN RAISE EXCEPTION 'forbidden'; END IF;
    IF v_action.status <> 'pending' THEN RAISE EXCEPTION 'action_not_pending'; END IF;
    IF v_action.assigned_to_org_user_id <> p_actor_org_user_id
       AND v_role NOT IN ('manager', 'company_admin', 'super_admin') THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    IF p_create_next AND NOT EXISTS (
        SELECT 1 FROM organization_users
        WHERE id = p_next_assigned_org_user_id
          AND organization_id = p_organization_id
          AND is_active = 1
    ) THEN
        RAISE EXCEPTION 'target_agent_not_found';
    END IF;
    SELECT channel_notes INTO v_channel
    FROM contacts
    WHERE lead_id = v_action.lead_id
    ORDER BY is_primary DESC, created_at
    LIMIT 1;
    SELECT name INTO v_touchpoint_type
    FROM action_types
    WHERE id = v_action.action_type_id
      AND organization_id = p_organization_id;

    -- A touchpoint here is a person: identity, role, and reachable channel.
    IF btrim(coalesce(p_contact_name, '')) <> '' OR
       btrim(coalesce(p_contact_role, '')) <> '' OR
       btrim(coalesce(p_contact_phone, '')) <> '' OR
       btrim(coalesce(p_contact_email, '')) <> '' OR
       btrim(coalesce(p_contact_whatsapp, '')) <> '' THEN
        IF btrim(coalesce(p_contact_name, '')) = '' OR
           btrim(coalesce(p_contact_role, '')) = '' OR
           (btrim(coalesce(p_contact_phone, '')) = '' AND
            btrim(coalesce(p_contact_email, '')) = '' AND
            btrim(coalesce(p_contact_whatsapp, '')) = '') THEN
            RAISE EXCEPTION 'contact_required';
        END IF;
        IF length(p_contact_name) > 200 OR length(p_contact_role) > 200 OR
           length(coalesce(p_contact_phone, '')) > 80 OR
           length(coalesce(p_contact_email, '')) > 254 OR
           length(coalesce(p_contact_whatsapp, '')) > 80 OR
           (btrim(coalesce(p_contact_email, '')) <> '' AND
            p_contact_email !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$') THEN
            RAISE EXCEPTION 'invalid_contact';
        END IF;
        v_contact_id := p_contact_id;
        INSERT INTO contacts (
            id, lead_id, full_name, role_title, phone_raw, phone_normalized,
            email, whatsapp, channel_notes, is_primary, created_at, updated_at
        ) VALUES (
            p_contact_id, v_action.lead_id, btrim(p_contact_name),
            btrim(p_contact_role), nullif(btrim(coalesce(p_contact_phone, '')), ''),
            nullif(regexp_replace(coalesce(p_contact_phone, ''), '\D+', '', 'g'), ''),
            nullif(lower(btrim(coalesce(p_contact_email, ''))), ''),
            nullif(btrim(coalesce(p_contact_whatsapp, '')), ''), NULL,
            CASE WHEN EXISTS (SELECT 1 FROM contacts WHERE lead_id = v_action.lead_id)
                THEN 0 ELSE 1 END, v_now, v_now
        );
    END IF;
    INSERT INTO touchpoints (
        id, organization_id, lead_id, action_id, org_user_id, contact_id,
        occurred_at, touchpoint_type, channel, outcome, note, decision_note,
        action_note, followup_note, next_due_date, source, source_detail,
        legacy_update_at, created_at
    ) VALUES (
        p_touchpoint_id, p_organization_id, v_action.lead_id, p_action_id,
        p_actor_org_user_id, v_contact_id, v_now, coalesce(v_touchpoint_type, 'Autre'),
        v_channel, p_outcome, nullif(btrim(coalesce(p_note, '')), ''),
        nullif(btrim(coalesce(p_decision, '')), ''), 'Oui',
        nullif(btrim(coalesce(p_next_comment, '')), ''), p_next_due_date,
        'manual', 'complete_action_native', NULL, v_now
    );
    UPDATE actions SET
        status = 'done',
        completed_at = v_now,
        completed_by_org_user_id = p_actor_org_user_id,
        completion_note = nullif(btrim(coalesce(p_note, '')), ''),
        updated_at = v_now
    WHERE id = p_action_id;
    IF btrim(coalesce(p_obstacle, '')) <> '' THEN
        UPDATE leads SET obstacle = btrim(p_obstacle), updated_at = v_now
        WHERE id = v_action.lead_id;
    END IF;
    IF btrim(coalesce(p_note, '')) <> '' THEN
        INSERT INTO comments (
            id, organization_id, lead_id, action_id, touchpoint_id, transfer_id,
            org_user_id, body, comment_type, visibility, source, source_column,
            is_pinned, is_system_import, created_at, updated_at
        ) VALUES (
            p_comment_id, p_organization_id, v_action.lead_id, p_action_id,
            p_touchpoint_id, NULL, p_actor_org_user_id, btrim(p_note),
            'action_note', 'team', 'manual', NULL, 0, 0, v_now, v_now
        );
    END IF;

    IF NOT p_create_next AND NOT EXISTS
       (SELECT 1 FROM actions WHERE lead_id = v_action.lead_id AND status = 'pending') THEN
        UPDATE leads SET churn_flag = 1, updated_at = v_now WHERE id = v_action.lead_id;
    END IF;
    IF p_create_next THEN
        SELECT id INTO v_next_type_id
        FROM action_types
        WHERE organization_id = p_organization_id AND is_active = 1
        ORDER BY CASE WHEN name = p_next_action_type_name THEN 0 ELSE 1 END,
                 position, name
        LIMIT 1;
        INSERT INTO actions (
            id, organization_id, lead_id, assigned_to_org_user_id,
            created_by_org_user_id, action_type_id, title, details, due_date,
            status, urgency_color_cache, completed_at, completed_by_org_user_id,
            completion_note, transferred_to_org_user_id, previous_action_id,
            created_at, updated_at
        ) VALUES (
            p_next_action_id, p_organization_id, v_action.lead_id,
            p_next_assigned_org_user_id, p_actor_org_user_id, v_next_type_id,
            coalesce(nullif(btrim(coalesce(p_next_title, '')), ''), 'Prochaine action'),
            nullif(btrim(coalesce(p_next_comment, '')), ''), p_next_due_date,
            'pending', NULL, NULL, NULL, NULL, NULL, p_action_id, v_now, v_now
        );
        UPDATE leads SET
            owner_org_user_id = p_next_assigned_org_user_id,
            churn_flag = 0, updated_at = v_now
        WHERE id = v_action.lead_id;
        IF btrim(coalesce(p_next_comment, '')) <> '' THEN
            INSERT INTO comments (
                id, organization_id, lead_id, action_id, touchpoint_id,
                transfer_id, org_user_id, body, comment_type, visibility,
                source, source_column, is_pinned, is_system_import, created_at,
                updated_at
            ) VALUES (
                p_next_comment_id, p_organization_id, v_action.lead_id,
                p_next_action_id, p_touchpoint_id, NULL, p_actor_org_user_id,
                btrim(p_next_comment), 'next_action_note', 'team', 'manual',
                NULL, 0, 0, v_now, v_now
            );
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'touchpointId', p_touchpoint_id,
        'nextActionId', CASE WHEN p_create_next THEN p_next_action_id ELSE NULL END
    );
END;
$$;


-- Atomic edit: the Edge Function checks the password, and this function
-- independently checks the actor, company, contact IDs, and field lengths.
CREATE OR REPLACE FUNCTION public.nexstep_mobile_update_lead(
    p_actor_org_user_id text, p_lead_id text, p_name text, p_city text,
    p_context_full text, p_contacts jsonb, p_audit_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_lead leads%ROWTYPE;
    v_actor record;
    v_contact jsonb;
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
BEGIN
    SELECT * INTO v_lead FROM leads WHERE id = p_lead_id AND is_archived = 0 FOR UPDATE;
    SELECT ou.organization_id, ou.role, u.is_global_admin INTO v_actor
    FROM organization_users ou JOIN users u ON u.id = ou.user_id
    WHERE ou.id = p_actor_org_user_id AND ou.is_active = 1 AND u.is_active = 1;
    IF v_lead.id IS NULL OR v_actor.organization_id IS NULL OR
       (coalesce(v_actor.is_global_admin, 0) = 0 AND
        (v_actor.organization_id <> v_lead.organization_id OR
         (v_actor.role NOT IN ('company_admin', 'super_admin') AND
          v_lead.owner_org_user_id <> p_actor_org_user_id))) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    IF btrim(coalesce(p_name, '')) = '' OR length(p_name) > 200 OR
       length(coalesce(p_city, '')) > 200 OR length(coalesce(p_context_full, '')) > 5000 THEN
        RAISE EXCEPTION 'invalid_lead';
    END IF;
    IF jsonb_typeof(p_contacts) <> 'array' OR
       jsonb_array_length(p_contacts) <> (SELECT count(*) FROM contacts WHERE lead_id = p_lead_id) OR
       EXISTS (SELECT 1 FROM jsonb_array_elements(p_contacts) c
               WHERE NOT EXISTS (SELECT 1 FROM contacts x WHERE x.id = c->>'id' AND x.lead_id = p_lead_id)) OR
       (SELECT count(DISTINCT c->>'id') FROM jsonb_array_elements(p_contacts) c) <> jsonb_array_length(p_contacts) THEN
        RAISE EXCEPTION 'contact_mismatch';
    END IF;
    UPDATE leads SET name = btrim(p_name),
        normalized_name = lower(regexp_replace(btrim(p_name), '\s+', ' ', 'g')),
        city = nullif(btrim(coalesce(p_city, '')), ''),
        context_full = nullif(btrim(coalesce(p_context_full, '')), ''), updated_at = v_now
    WHERE id = p_lead_id;
    FOR v_contact IN SELECT value FROM jsonb_array_elements(p_contacts) LOOP
        IF length(coalesce(v_contact->>'full_name', '')) > 200 OR
           length(coalesce(v_contact->>'role_title', '')) > 200 OR
           length(coalesce(v_contact->>'phone_raw', '')) > 80 OR
           length(coalesce(v_contact->>'email', '')) > 254 OR
           length(coalesce(v_contact->>'whatsapp', '')) > 80 OR
           length(coalesce(v_contact->>'channel_notes', '')) > 500 OR
           (coalesce(v_contact->>'email', '') <> '' AND
            (v_contact->>'email') !~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$') THEN
            RAISE EXCEPTION 'invalid_contact';
        END IF;
        UPDATE contacts SET full_name = nullif(btrim(v_contact->>'full_name'), ''),
            role_title = nullif(btrim(v_contact->>'role_title'), ''),
            phone_raw = nullif(btrim(v_contact->>'phone_raw'), ''),
            phone_normalized = nullif(regexp_replace(coalesce(v_contact->>'phone_raw',''), '\D+', '', 'g'), ''),
            email = nullif(lower(btrim(v_contact->>'email')), ''),
            whatsapp = nullif(btrim(v_contact->>'whatsapp'), ''),
            channel_notes = nullif(btrim(v_contact->>'channel_notes'), ''),
            updated_at = v_now
        WHERE id = v_contact->>'id' AND lead_id = p_lead_id;
    END LOOP;
    INSERT INTO audit_logs (id, organization_id, actor_org_user_id, entity_type,
        entity_id, action, after_json, created_at)
    VALUES (p_audit_id, v_lead.organization_id, p_actor_org_user_id, 'lead',
        p_lead_id, 'edit_details', jsonb_build_object('contact_count', jsonb_array_length(p_contacts))::text, v_now);
    RETURN jsonb_build_object('leadId', p_lead_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_reactivate_lead(
    p_actor_org_user_id text, p_lead_id text, p_reason text, p_title text,
    p_due_date text, p_action_type_id text, p_action_id text, p_comment_id text,
    p_audit_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_lead leads%ROWTYPE;
    v_actor record;
    v_previous text;
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
BEGIN
    SELECT * INTO v_lead FROM leads WHERE id = p_lead_id AND is_archived = 0 FOR UPDATE;
    SELECT ou.organization_id, ou.role, u.is_global_admin INTO v_actor
    FROM organization_users ou JOIN users u ON u.id = ou.user_id
    WHERE ou.id = p_actor_org_user_id AND ou.is_active = 1 AND u.is_active = 1;
    IF v_lead.id IS NULL OR v_actor.organization_id IS NULL OR
       (coalesce(v_actor.is_global_admin, 0) = 0 AND
        (v_actor.organization_id <> v_lead.organization_id OR
         (v_actor.role NOT IN ('company_admin', 'super_admin') AND
          v_lead.owner_org_user_id <> p_actor_org_user_id))) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    IF btrim(coalesce(p_reason,'')) = '' OR length(p_reason) > 2000 OR
       btrim(coalesce(p_title,'')) = '' OR length(p_title) > 200 THEN
        RAISE EXCEPTION 'reason_or_action_required';
    END IF;
    IF EXISTS (SELECT 1 FROM actions WHERE lead_id = p_lead_id AND status = 'pending') THEN
        RAISE EXCEPTION 'already_active';
    END IF;
    SELECT id INTO v_previous FROM actions WHERE lead_id = p_lead_id
    ORDER BY created_at DESC LIMIT 1;
    IF v_previous IS NULL AND v_lead.churn_flag = 0 THEN RAISE EXCEPTION 'not_stopped'; END IF;
    IF p_action_type_id IS NOT NULL AND NOT EXISTS
       (SELECT 1 FROM action_types WHERE id = p_action_type_id AND organization_id = v_lead.organization_id AND is_active = 1) THEN
        RAISE EXCEPTION 'invalid_action_type';
    END IF;
    INSERT INTO actions (id, organization_id, lead_id, assigned_to_org_user_id,
        created_by_org_user_id, action_type_id, title, due_date, status,
        previous_action_id, created_at, updated_at)
    VALUES (p_action_id, v_lead.organization_id, p_lead_id,
        coalesce(v_lead.owner_org_user_id, p_actor_org_user_id), p_actor_org_user_id,
        p_action_type_id, btrim(p_title), p_due_date, 'pending', v_previous, v_now, v_now);
    UPDATE leads SET churn_flag = 0, updated_at = v_now WHERE id = p_lead_id;
    INSERT INTO comments (id, organization_id, lead_id, action_id, org_user_id,
        body, comment_type, visibility, source, created_at, updated_at)
    VALUES (p_comment_id, v_lead.organization_id, p_lead_id, p_action_id,
        p_actor_org_user_id, btrim(p_reason), 'reactivation_reason', 'team', 'manual', v_now, v_now);
    INSERT INTO audit_logs (id, organization_id, actor_org_user_id, entity_type,
        entity_id, action, after_json, created_at)
    VALUES (p_audit_id, v_lead.organization_id, p_actor_org_user_id, 'lead',
        p_lead_id, 'reactivate', jsonb_build_object('action_id', p_action_id)::text, v_now);
    RETURN jsonb_build_object('actionId', p_action_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_set_company_admin(
    p_actor_user_id text, p_target_org_user_id text, p_enabled boolean, p_audit_id text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
    v_target organization_users%ROWTYPE;
    v_role text;
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users WHERE id = p_actor_user_id AND is_global_admin = 1 AND is_active = 1) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    SELECT * INTO v_target FROM organization_users WHERE id = p_target_org_user_id FOR UPDATE;
    IF v_target.id IS NULL OR v_target.is_active <> 1 OR
       v_target.role NOT IN ('agent', 'company_admin') THEN
        RAISE EXCEPTION 'invalid_agent';
    END IF;
    v_role := CASE WHEN p_enabled THEN 'company_admin' ELSE 'agent' END;
    UPDATE organization_users SET role = v_role,
        can_view_team = CASE WHEN p_enabled THEN 1 ELSE 0 END, updated_at = v_now
    WHERE id = p_target_org_user_id;
    INSERT INTO audit_logs (id, organization_id, actor_user_id, entity_type,
        entity_id, action, after_json, created_at)
    VALUES (p_audit_id, v_target.organization_id, p_actor_user_id, 'organization_user',
        p_target_org_user_id, 'set_company_administrator', jsonb_build_object('role', v_role)::text, v_now);
    RETURN jsonb_build_object('orgUserId', p_target_org_user_id, 'role', v_role);
END;
$$;

DO $$
DECLARE v_function regprocedure;
BEGIN
    FOR v_function IN SELECT p.oid::regprocedure FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.proname IN
        ('nexstep_mobile_complete_action_v2', 'nexstep_mobile_update_lead',
         'nexstep_mobile_reactivate_lead', 'nexstep_mobile_set_company_admin')
    LOOP
        EXECUTE format('REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated', v_function);
        EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO service_role', v_function);
    END LOOP;
END;
$$;
COMMIT;
