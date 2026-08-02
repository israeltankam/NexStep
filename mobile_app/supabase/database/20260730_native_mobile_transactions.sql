-- NexStep native mobile transaction helpers.
--
-- This migration is additive: it creates private functions only. It does not
-- recreate, truncate, or alter any existing table or user data. Edge Functions
-- call these helpers with the server-side secret role so multi-table writes
-- remain atomic.

BEGIN;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_create_lead(
    p_organization_id text,
    p_actor_org_user_id text,
    p_lead_name text,
    p_category_name text,
    p_contacts jsonb,
    p_city text,
    p_context_note text,
    p_action_type_name text,
    p_action_title text,
    p_due_date text,
    p_action_details text,
    p_lead_id text,
    p_action_id text,
    p_comment_id text,
    p_contact_ids jsonb
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
    v_normalized_name text;
    v_stage_id text;
    v_status_id text;
    v_category_id text;
    v_action_type_id text;
    v_duplicate_group text;
    v_contact jsonb;
    v_contact_id text;
    v_contact_ids jsonb := '[]'::jsonb;
    v_ordinality bigint;
    v_comment_body text;
BEGIN
    IF btrim(coalesce(p_lead_name, '')) = '' THEN
        RAISE EXCEPTION 'lead_name_required';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM organization_users ou
        JOIN users u ON u.id = ou.user_id
        WHERE ou.id = p_actor_org_user_id
          AND ou.organization_id = p_organization_id
          AND ou.is_active = 1
          AND u.is_active = 1
    ) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;

    v_normalized_name := lower(regexp_replace(btrim(p_lead_name), '\s+', ' ', 'g'));
    SELECT id INTO v_stage_id
    FROM pipeline_stages
    WHERE organization_id = p_organization_id AND is_active = 1
    ORDER BY CASE WHEN name = 'Nouveau lead' THEN 0 ELSE 1 END, position, name
    LIMIT 1;
    SELECT id INTO v_status_id
    FROM lead_statuses
    WHERE organization_id = p_organization_id AND is_active = 1
    ORDER BY CASE WHEN name = 'Nouveau' THEN 0 ELSE 1 END, position, name
    LIMIT 1;
    SELECT id INTO v_category_id
    FROM client_categories
    WHERE organization_id = p_organization_id
      AND is_active = 1
      AND name = p_category_name
    LIMIT 1;
    SELECT id INTO v_action_type_id
    FROM action_types
    WHERE organization_id = p_organization_id AND is_active = 1
    ORDER BY CASE WHEN name = p_action_type_name THEN 0 WHEN name = 'Appel' THEN 1 ELSE 2 END,
             position, name
    LIMIT 1;
    IF EXISTS (
        SELECT 1 FROM leads
        WHERE organization_id = p_organization_id
          AND normalized_name = v_normalized_name
    ) THEN
        v_duplicate_group := regexp_replace(v_normalized_name, '[^a-z0-9]+', '-', 'g');
    END IF;

    INSERT INTO leads (
        id, organization_id, name, normalized_name, owner_org_user_id,
        stage_id, status_id, category_id, city, address, latitude, longitude,
        score, source, source_detail, obstacle, context_full,
        prioritization_reason, churn_flag, legacy_rank, legacy_row_number,
        legacy_age_days, legacy_touchpoint_count, legacy_fields_json,
        possible_duplicate_group, is_archived, created_at, updated_at
    ) VALUES (
        p_lead_id, p_organization_id, btrim(p_lead_name), v_normalized_name,
        p_actor_org_user_id, v_stage_id, v_status_id, v_category_id,
        nullif(btrim(coalesce(p_city, '')), ''), NULL, NULL, NULL, 0,
        'manual', 'NexStep Android', NULL,
        nullif(btrim(coalesce(p_context_note, '')), ''), NULL, 0,
        NULL, NULL, NULL, NULL,
        jsonb_build_object(
            'created_from', 'native_mobile',
            'created_by_org_user_id', p_actor_org_user_id
        )::text,
        v_duplicate_group, 0, v_now, v_now
    );

    FOR v_contact, v_ordinality IN
        SELECT value, ordinality
        FROM jsonb_array_elements(coalesce(p_contacts, '[]'::jsonb))
             WITH ORDINALITY
        LIMIT 5
    LOOP
        IF btrim(
            coalesce(v_contact->>'full_name', '') ||
            coalesce(v_contact->>'role_title', '') ||
            coalesce(v_contact->>'phone_raw', '') ||
            coalesce(v_contact->>'email', '') ||
            coalesce(v_contact->>'whatsapp', '') ||
            coalesce(v_contact->>'channel_notes', '')
        ) = '' THEN
            CONTINUE;
        END IF;
        v_contact_id := p_contact_ids ->> ((v_ordinality - 1)::integer);
        IF coalesce(v_contact_id, '') = '' THEN
            RAISE EXCEPTION 'contact_id_missing';
        END IF;
        INSERT INTO contacts (
            id, lead_id, full_name, role_title, phone_raw, phone_normalized,
            email, whatsapp, channel_notes, is_primary, created_at, updated_at
        ) VALUES (
            v_contact_id, p_lead_id,
            nullif(btrim(coalesce(v_contact->>'full_name', '')), ''),
            nullif(btrim(coalesce(v_contact->>'role_title', '')), ''),
            nullif(btrim(coalesce(v_contact->>'phone_raw', '')), ''),
            nullif(regexp_replace(coalesce(v_contact->>'phone_raw', ''), '\D+', '', 'g'), ''),
            nullif(btrim(coalesce(v_contact->>'email', '')), ''),
            nullif(btrim(coalesce(v_contact->>'whatsapp', '')), ''),
            nullif(btrim(coalesce(v_contact->>'channel_notes', '')), ''),
            CASE WHEN jsonb_array_length(v_contact_ids) = 0 THEN 1 ELSE 0 END,
            v_now, v_now
        );
        IF jsonb_array_length(v_contact_ids) = 0 THEN
            v_contact_ids := jsonb_build_array(v_contact_id);
        ELSE
            v_contact_ids := v_contact_ids || jsonb_build_array(v_contact_id);
        END IF;
    END LOOP;

    INSERT INTO actions (
        id, organization_id, lead_id, assigned_to_org_user_id,
        created_by_org_user_id, action_type_id, title, details, due_date,
        status, urgency_color_cache, completed_at, completed_by_org_user_id,
        completion_note, transferred_to_org_user_id, previous_action_id,
        created_at, updated_at
    ) VALUES (
        p_action_id, p_organization_id, p_lead_id, p_actor_org_user_id,
        p_actor_org_user_id, v_action_type_id,
        coalesce(nullif(btrim(coalesce(p_action_title, '')), ''), p_action_type_name, 'Première action'),
        nullif(btrim(coalesce(p_action_details, '')), ''), p_due_date,
        'pending', NULL, NULL, NULL, NULL, NULL, NULL, v_now, v_now
    );

    v_comment_body := concat_ws(
        E'\n\n',
        nullif(btrim(coalesce(p_context_note, '')), ''),
        nullif(btrim(coalesce(p_action_details, '')), '')
    );
    IF btrim(v_comment_body) <> '' THEN
        INSERT INTO comments (
            id, organization_id, lead_id, action_id, touchpoint_id,
            transfer_id, org_user_id, body, comment_type, visibility,
            source, source_column, is_pinned, is_system_import, created_at,
            updated_at
        ) VALUES (
            p_comment_id, p_organization_id, p_lead_id, p_action_id, NULL,
            NULL, p_actor_org_user_id, v_comment_body, 'general', 'team',
            'manual', NULL, 0, 0, v_now, v_now
        );
    END IF;

    RETURN jsonb_build_object(
        'leadId', p_lead_id,
        'actionId', p_action_id,
        'contactIds', v_contact_ids,
        'commentId', CASE WHEN btrim(v_comment_body) <> '' THEN p_comment_id ELSE NULL END
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_add_comment(
    p_organization_id text,
    p_actor_org_user_id text,
    p_lead_id text,
    p_action_id text,
    p_comment_id text,
    p_body text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
BEGIN
    IF btrim(coalesce(p_body, '')) = '' THEN
        RAISE EXCEPTION 'comment_empty';
    END IF;
    IF NOT EXISTS (
        SELECT 1
        FROM organization_users
        WHERE id = p_actor_org_user_id
          AND organization_id = p_organization_id
          AND is_active = 1
    ) OR NOT EXISTS (
        SELECT 1 FROM leads
        WHERE id = p_lead_id AND organization_id = p_organization_id
    ) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    INSERT INTO comments (
        id, organization_id, lead_id, action_id, touchpoint_id, transfer_id,
        org_user_id, body, comment_type, visibility, source, source_column,
        is_pinned, is_system_import, created_at, updated_at
    ) VALUES (
        p_comment_id, p_organization_id, p_lead_id, p_action_id, NULL, NULL,
        p_actor_org_user_id, btrim(p_body), 'general', 'team', 'manual', NULL,
        0, 0, v_now, v_now
    );
    RETURN jsonb_build_object('commentId', p_comment_id);
END;
$$;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_complete_action(
    p_organization_id text,
    p_actor_org_user_id text,
    p_action_id text,
    p_outcome text,
    p_note text,
    p_contact_name text,
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

    INSERT INTO touchpoints (
        id, organization_id, lead_id, action_id, org_user_id, contact_id,
        occurred_at, touchpoint_type, channel, outcome, note, decision_note,
        action_note, followup_note, next_due_date, source, source_detail,
        legacy_update_at, created_at
    ) VALUES (
        p_touchpoint_id, p_organization_id, v_action.lead_id, p_action_id,
        p_actor_org_user_id, NULL, v_now, coalesce(v_touchpoint_type, 'Autre'),
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
    IF btrim(coalesce(p_contact_name, '')) <> ''
       AND NOT EXISTS (SELECT 1 FROM contacts WHERE lead_id = v_action.lead_id) THEN
        INSERT INTO contacts (
            id, lead_id, full_name, role_title, phone_raw, phone_normalized,
            email, whatsapp, channel_notes, is_primary, created_at, updated_at
        ) VALUES (
            p_contact_id, v_action.lead_id, btrim(p_contact_name), NULL, NULL,
            NULL, NULL, NULL, NULL, 1, v_now, v_now
        );
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
            updated_at = v_now
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

CREATE OR REPLACE FUNCTION public.nexstep_mobile_transfer_action(
    p_organization_id text,
    p_actor_org_user_id text,
    p_action_id text,
    p_target_org_user_id text,
    p_transfer_note text,
    p_transfer_id text,
    p_new_action_id text,
    p_comment_id text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
    v_today text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD');
    v_action actions%ROWTYPE;
BEGIN
    SELECT * INTO v_action
    FROM actions
    WHERE id = p_action_id AND organization_id = p_organization_id
    FOR UPDATE;
    IF v_action.id IS NULL OR v_action.status <> 'pending'
       OR v_action.assigned_to_org_user_id <> p_actor_org_user_id THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM organization_users
        WHERE id = p_target_org_user_id
          AND organization_id = p_organization_id
          AND is_active = 1
    ) THEN
        RAISE EXCEPTION 'target_agent_not_found';
    END IF;

    INSERT INTO transfers (
        id, organization_id, lead_id, action_id, from_org_user_id,
        to_org_user_id, transfer_note, created_at
    ) VALUES (
        p_transfer_id, p_organization_id, v_action.lead_id, p_action_id,
        p_actor_org_user_id, p_target_org_user_id,
        nullif(btrim(coalesce(p_transfer_note, '')), ''), v_now
    );
    UPDATE actions SET
        status = 'transferred',
        transferred_to_org_user_id = p_target_org_user_id,
        updated_at = v_now
    WHERE id = p_action_id;
    INSERT INTO actions (
        id, organization_id, lead_id, assigned_to_org_user_id,
        created_by_org_user_id, action_type_id, title, details, due_date,
        status, urgency_color_cache, completed_at, completed_by_org_user_id,
        completion_note, transferred_to_org_user_id, previous_action_id,
        created_at, updated_at
    ) VALUES (
        p_new_action_id, p_organization_id, v_action.lead_id,
        p_target_org_user_id, p_actor_org_user_id, v_action.action_type_id,
        v_action.title,
        coalesce(nullif(btrim(coalesce(p_transfer_note, '')), ''), v_action.details),
        v_today, 'pending', NULL, NULL, NULL, NULL, NULL, p_action_id,
        v_now, v_now
    );
    UPDATE leads SET owner_org_user_id = p_target_org_user_id, updated_at = v_now
    WHERE id = v_action.lead_id;
    IF btrim(coalesce(p_transfer_note, '')) <> '' THEN
        INSERT INTO comments (
            id, organization_id, lead_id, action_id, touchpoint_id, transfer_id,
            org_user_id, body, comment_type, visibility, source, source_column,
            is_pinned, is_system_import, created_at, updated_at
        ) VALUES (
            p_comment_id, p_organization_id, v_action.lead_id, p_action_id,
            NULL, p_transfer_id, p_actor_org_user_id, btrim(p_transfer_note),
            'transfer_note', 'team', 'manual', NULL, 0, 0, v_now, v_now
        );
    END IF;
    RETURN jsonb_build_object(
        'transferId', p_transfer_id,
        'newActionId', p_new_action_id
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.nexstep_mobile_review_password_reset(
    p_request_id text,
    p_organization_id text,
    p_reviewer_user_id text,
    p_reviewer_org_user_id text,
    p_approve boolean,
    p_audit_id text
) RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_now text := to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.MS"+00:00"');
    v_request password_reset_requests%ROWTYPE;
    v_role text;
BEGIN
    SELECT role INTO v_role
    FROM organization_users
    WHERE id = p_reviewer_org_user_id
      AND user_id = p_reviewer_user_id
      AND organization_id = p_organization_id
      AND is_active = 1;
    IF v_role NOT IN ('company_admin', 'super_admin')
       AND NOT EXISTS (
           SELECT 1 FROM users
           WHERE id = p_reviewer_user_id AND is_global_admin = 1
       ) THEN
        RAISE EXCEPTION 'forbidden';
    END IF;
    SELECT * INTO v_request
    FROM password_reset_requests
    WHERE id = p_request_id
      AND organization_id = p_organization_id
      AND status = 'pending'
    FOR UPDATE;
    IF v_request.id IS NULL THEN RAISE EXCEPTION 'request_not_found'; END IF;

    IF p_approve THEN
        UPDATE users SET
            password_hash = NULL,
            password_set_at = NULL,
            must_change_password = 0,
            updated_at = v_now
        WHERE id = v_request.user_id;
        UPDATE auth_sessions SET revoked_at = v_now
        WHERE user_id = v_request.user_id AND revoked_at IS NULL;
    END IF;
    UPDATE password_reset_requests SET
        status = CASE WHEN p_approve THEN 'approved' ELSE 'rejected' END,
        reviewed_at = v_now,
        reviewed_by_user_id = p_reviewer_user_id
    WHERE id = p_request_id;
    INSERT INTO audit_logs (
        id, organization_id, actor_user_id, actor_org_user_id, entity_type,
        entity_id, action, before_json, after_json, created_at
    ) VALUES (
        p_audit_id, p_organization_id, p_reviewer_user_id,
        p_reviewer_org_user_id, 'password_reset_request', p_request_id,
        CASE WHEN p_approve THEN 'approve' ELSE 'reject' END,
        '{"status":"pending"}',
        CASE WHEN p_approve THEN '{"status":"approved"}' ELSE '{"status":"rejected"}' END,
        v_now
    );
    RETURN jsonb_build_object(
        'requestId', p_request_id,
        'status', CASE WHEN p_approve THEN 'approved' ELSE 'rejected' END
    );
END;
$$;

DO $$
DECLARE
    v_function regprocedure;
BEGIN
    FOR v_function IN
        SELECT p.oid::regprocedure
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public'
          AND p.proname LIKE 'nexstep_mobile_%'
    LOOP
        EXECUTE format(
            'REVOKE ALL ON FUNCTION %s FROM PUBLIC, anon, authenticated',
            v_function
        );
        EXECUTE format(
            'GRANT EXECUTE ON FUNCTION %s TO service_role',
            v_function
        );
    END LOOP;
END;
$$;

COMMIT;
