import { hmacHex, normalizePin, verifyStoredSecret } from "./crypto.ts";
import { isAdministrator } from "./auth.ts";
import { pinPepper, requireData } from "./client.ts";
import { parseContactPayload } from "./contact.ts";
import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { newId, nowIso, text } from "./types.ts";

const actionNames: Record<string, string | null> = {
  call: "Appel",
  message: "WhatsApp",
  visit: "Visite",
  meeting: "Rendez-vous",
  none: null,
};

const outcomeNames: Record<string, string> = {
  interested: "Intéressé",
  callback: "À relancer",
  unavailable: "Pas disponible",
  refusal: "Refus",
};

function contacts(payload: JsonObject): JsonObject[] {
  if (!Array.isArray(payload.contacts)) return [];
  return payload.contacts.slice(0, 5).map((contact) => {
    const source = contact as JsonObject;
    return {
      full_name: text(source.fullName).trim(),
      role_title: text(source.roleTitle).trim(),
      phone_raw: text(source.phone).trim(),
      email: text(source.email).trim(),
      whatsapp: text(source.whatsapp).trim(),
      channel_notes: text(source.notes).trim(),
    };
  });
}

export async function createLead(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const leadName = text(payload.name).trim();
  if (!leadName) return { status: 400, error: "lead_name_required" };
  const suppliedContacts = contacts(payload);
  const contactIds = suppliedContacts.map(() => newId());
  const actionKey = text(payload.actionKey);
  const actionTypeName = actionNames[actionKey] || "Appel";
  const result = await context.db.rpc("nexstep_mobile_create_lead", {
    p_organization_id: context.organization.id,
    p_actor_org_user_id: context.orgUser.id,
    p_lead_name: leadName,
    p_category_name: text(payload.categoryName) || null,
    p_contacts: suppliedContacts,
    p_city: text(payload.city),
    p_context_note: text(payload.contextNote),
    p_action_type_name: actionTypeName,
    p_action_title: text(payload.actionTitle) || actionTypeName,
    p_due_date: payload.dueDate || null,
    p_action_details: text(payload.actionDetails),
    p_lead_id: newId(),
    p_action_id: newId(),
    p_comment_id: newId(),
    p_contact_ids: contactIds,
  });
  return { data: requireData(result) };
}

export async function addComment(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const body = text(payload.body).trim();
  if (!body) return { status: 400, error: "comment_empty" };
  const result = await context.db.rpc("nexstep_mobile_add_comment", {
    p_organization_id: context.organization.id,
    p_actor_org_user_id: context.orgUser.id,
    p_lead_id: text(payload.leadId),
    p_action_id: text(payload.actionId) || null,
    p_comment_id: newId(),
    p_body: body,
  });
  return { data: requireData(result) };
}

export async function addContact(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const parsed = parseContactPayload(payload);
  if (parsed.error) return { status: 400, error: parsed.error };

  const leadId = text(payload.leadId);
  const actionId = text(payload.actionId);
  if (!leadId || !actionId) return { status: 400, error: "contact_context_required" };

  const organizationId = text(context.organization.id);
  const [leadResult, actionResult] = await Promise.all([
    context.db.from("leads").select("id").eq("id", leadId)
      .eq("organization_id", organizationId).eq("is_archived", 0).maybeSingle(),
    context.db.from("actions").select("id,lead_id,assigned_to_org_user_id")
      .eq("id", actionId).eq("organization_id", organizationId).maybeSingle(),
  ]);
  if (leadResult.error || actionResult.error) throw new Error("database_error");
  if (!leadResult.data || !actionResult.data || actionResult.data.lead_id !== leadId) {
    return { status: 404, error: "lead_not_found" };
  }
  if (
    text(actionResult.data.assigned_to_org_user_id) !== text(context.orgUser.id) &&
    !isAdministrator(context)
  ) {
    return { status: 403, error: "forbidden" };
  }

  const existingResult = await context.db.from("contacts").select("id")
    .eq("lead_id", leadId).limit(1);
  if (existingResult.error) throw new Error("database_error");
  const now = nowIso();
  const contact = requireData(await context.db.from("contacts").insert({
    id: newId(),
    lead_id: leadId,
    ...parsed.contact,
    is_primary: (existingResult.data ?? []).length === 0 ? 1 : 0,
    created_at: now,
    updated_at: now,
  }).select("*").single());

  return { data: { contact } };
}

async function resolveTarget(
  context: SessionContext,
  agentPin: string,
): Promise<JsonObject | null> {
  const pepper = pinPepper();
  const lookup = await hmacHex(pepper, normalizePin(agentPin));
  const target = await context.db.from("organization_users").select("*")
    .eq("organization_id", context.organization.id)
    .eq("agent_pin_lookup", lookup)
    .eq("is_active", 1)
    .maybeSingle();
  if (!target.data) return null;
  const valid = await verifyStoredSecret(
    agentPin,
    text(target.data.agent_pin_hash),
    { normalize: true, pepper },
  );
  if (!valid) return null;
  const user = await context.db.from("users").select("display_name")
    .eq("id", target.data.user_id)
    .maybeSingle();
  return {
    ...target.data as JsonObject,
    display_name: user.data?.display_name || "",
  };
}

export async function completeAction(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const person = text(payload.contactName).trim();
  const role = text(payload.contactRole).trim();
  const phone = text(payload.contactPhone).trim();
  const email = text(payload.contactEmail).trim();
  const whatsapp = text(payload.contactWhatsapp).trim();
  const addingPerson = [person, role, phone, email, whatsapp].some(Boolean);
  if (addingPerson && (!person || !role || ![phone, email, whatsapp].some(Boolean))) {
    return { status: 400, error: "touchpoint_required" };
  }
  if (person.length > 200 || role.length > 200 || phone.length > 80 ||
      email.length > 254 || whatsapp.length > 80) {
    return { status: 400, error: "field_too_long" };
  }
  if (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return { status: 400, error: "invalid_email" };
  }
  const nextActionKey = text(payload.nextActionKey);
  const nextActionType = actionNames[nextActionKey] ?? null;
  let nextAssigned = text(context.orgUser.id);
  const targetPin = text(payload.targetAgentPin).trim();
  if (targetPin) {
    const target = await resolveTarget(context, targetPin);
    if (!target) return { status: 404, error: "target_agent_not_found" };
    nextAssigned = text(target.id);
  }

  const result = await context.db.rpc("nexstep_mobile_complete_action_v2", {
    p_organization_id: context.organization.id,
    p_actor_org_user_id: context.orgUser.id,
    p_action_id: text(payload.actionId),
    p_outcome: outcomeNames[text(payload.outcomeKey)] || text(payload.outcomeKey),
    p_note: text(payload.note),
    p_contact_name: text(payload.contactName),
    p_contact_role: text(payload.contactRole),
    p_contact_phone: text(payload.contactPhone),
    p_contact_email: text(payload.contactEmail),
    p_contact_whatsapp: text(payload.contactWhatsapp),
    p_obstacle: text(payload.obstacle),
    p_decision: text(payload.decision),
    p_create_next: nextActionType !== null,
    p_next_due_date: payload.nextDueDate || null,
    p_next_action_type_name: nextActionType,
    p_next_title: text(payload.nextTitle) || nextActionType,
    p_next_comment: text(payload.nextComment),
    p_next_assigned_org_user_id: nextAssigned,
    p_touchpoint_id: newId(),
    p_next_action_id: newId(),
    p_contact_id: newId(),
    p_comment_id: newId(),
    p_next_comment_id: newId(),
  });
  return { data: requireData(result) };
}

export async function transferAction(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const target = await resolveTarget(context, text(payload.targetAgentPin));
  if (!target) return { status: 404, error: "target_agent_not_found" };
  const result = await context.db.rpc("nexstep_mobile_transfer_action", {
    p_organization_id: context.organization.id,
    p_actor_org_user_id: context.orgUser.id,
    p_action_id: text(payload.actionId),
    p_target_org_user_id: target.id,
    p_transfer_note: text(payload.note),
    p_transfer_id: newId(),
    p_new_action_id: newId(),
    p_comment_id: newId(),
  });
  return {
    data: {
      ...requireData(result) as JsonObject,
      targetName: text(target.display_name),
    },
  };
}

export async function setLanguage(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const language = text(payload.language) === "en" ? "en" : "fr";
  requireData(await context.db.from("users").update({
    preferred_language: language,
    updated_at: nowIso(),
  }).eq("id", context.user.id).select("id").single());
  return { data: { language } };
}

export async function logout(context: SessionContext): Promise<ApiResult> {
  requireData(await context.db.from("auth_sessions").update({
    revoked_at: nowIso(),
  }).eq("id", context.sessionId).select("id").single());
  return { data: { loggedOut: true } };
}

export async function reviewPasswordReset(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  if (!isAdministrator(context)) return { status: 403, error: "forbidden" };
  const requestResult = await context.db.from("password_reset_requests")
    .select("id,organization_id")
    .eq("id", text(payload.requestId))
    .eq("status", "pending")
    .maybeSingle();
  if (requestResult.error) throw new Error("database_error");
  if (!requestResult.data) return { status: 404, error: "request_not_found" };

  const requestOrganizationId = text(requestResult.data.organization_id);
  if (
    !context.user.is_global_admin &&
    requestOrganizationId !== text(context.organization.id)
  ) {
    return { status: 403, error: "forbidden" };
  }
  const result = await context.db.rpc("nexstep_mobile_review_password_reset", {
    p_request_id: text(payload.requestId),
    p_organization_id: requestOrganizationId,
    p_reviewer_user_id: context.user.id,
    p_reviewer_org_user_id: context.orgUser.id,
    p_approve: Boolean(payload.approve),
    p_audit_id: newId(),
  });
  return { data: requireData(result) };
}
