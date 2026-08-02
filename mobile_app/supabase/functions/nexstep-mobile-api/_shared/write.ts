import { hmacHex, normalizePin, verifyStoredSecret } from "./crypto.ts";
import { isAdministrator } from "./auth.ts";
import { pinPepper, requireData } from "./client.ts";
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
  const nextActionKey = text(payload.nextActionKey);
  const nextActionType = actionNames[nextActionKey] ?? null;
  let nextAssigned = text(context.orgUser.id);
  const targetPin = text(payload.targetAgentPin).trim();
  if (targetPin) {
    const target = await resolveTarget(context, targetPin);
    if (!target) return { status: 404, error: "target_agent_not_found" };
    nextAssigned = text(target.id);
  }

  const result = await context.db.rpc("nexstep_mobile_complete_action", {
    p_organization_id: context.organization.id,
    p_actor_org_user_id: context.orgUser.id,
    p_action_id: text(payload.actionId),
    p_outcome: outcomeNames[text(payload.outcomeKey)] || text(payload.outcomeKey),
    p_note: text(payload.note),
    p_contact_name: text(payload.contactName),
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
