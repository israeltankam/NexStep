/** Sensitive lead operations; every request is checked against the session. */

import { verifyStoredSecret } from "./crypto.ts";
import { requireData } from "./client.ts";
import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { newId, text } from "./types.ts";

async function editableLead(context: SessionContext, leadId: string): Promise<JsonObject | null> {
  const result = await context.db.from("leads").select("*")
    .eq("id", leadId).eq("is_archived", 0).maybeSingle();
  if (result.error) throw new Error("database_error");
  const lead = result.data as JsonObject | null;
  if (!lead) return null;
  const global = Boolean(context.user.is_global_admin);
  const companyAdmin = ["company_admin", "super_admin"].includes(text(context.orgUser.role));
  if (!global && text(lead.organization_id) !== text(context.organization.id)) return null;
  if (!global && !companyAdmin &&
      text(lead.owner_org_user_id) !== text(context.orgUser.id)) return null;
  return lead;
}

export async function updateLead(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  const leadId = text(payload.leadId);
  if (!await editableLead(context, leadId)) return { status: 403, error: "forbidden" };
  const valid = await verifyStoredSecret(text(payload.password),
    text(context.user.password_hash), { normalize: false, pepper: null });
  if (!valid) return { status: 403, error: "invalid_password" };
  const name = text(payload.name).trim();
  const city = text(payload.city).trim();
  const details = text(payload.contextFull).trim();
  const contacts = Array.isArray(payload.contacts) ? payload.contacts as JsonObject[] : [];
  if (!name || name.length > 200 || city.length > 200 || details.length > 5000) {
    return { status: 400, error: "invalid_lead" };
  }
  for (const contact of contacts) {
    const email = text(contact.email).trim();
    if (text(contact.full_name).length > 200 || text(contact.role_title).length > 200 ||
        text(contact.phone_raw).length > 80 || email.length > 254 ||
        text(contact.whatsapp).length > 80 || text(contact.channel_notes).length > 500 ||
        (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))) {
      return { status: 400, error: "invalid_contact" };
    }
  }
  return { data: requireData(await context.db.rpc("nexstep_mobile_update_lead", {
    p_actor_org_user_id: context.orgUser.id, p_lead_id: leadId,
    p_name: name, p_city: city, p_context_full: details,
    p_contacts: contacts, p_audit_id: newId(),
  })) };
}

export async function reactivateLead(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  const leadId = text(payload.leadId);
  if (!await editableLead(context, leadId)) return { status: 403, error: "forbidden" };
  const reason = text(payload.reason).trim();
  const title = text(payload.title).trim();
  if (!reason || reason.length > 2000 || !title || title.length > 200) {
    return { status: 400, error: "reason_or_action_required" };
  }
  return { data: requireData(await context.db.rpc("nexstep_mobile_reactivate_lead", {
    p_actor_org_user_id: context.orgUser.id, p_lead_id: leadId,
    p_reason: reason, p_title: title, p_due_date: payload.dueDate || null,
    p_action_type_id: payload.actionTypeId || null, p_action_id: newId(),
    p_comment_id: newId(), p_audit_id: newId(),
  })) };
}

export async function companyAgents(context: SessionContext): Promise<ApiResult> {
  if (!context.user.is_global_admin) return { status: 403, error: "forbidden" };
  const [links, users, organizations] = await Promise.all([
    context.db.from("organization_users").select("id,organization_id,user_id,role,is_active")
      .eq("is_active", 1).in("role", ["agent", "company_admin"]).limit(5000),
    context.db.from("users").select("id,display_name,is_active").eq("is_active", 1).limit(5000),
    context.db.from("organizations").select("id,name,display_name").limit(1000),
  ]);
  if (links.error || users.error || organizations.error) throw new Error("database_error");
  const people = new Map((users.data ?? []).map((user) => [text(user.id), text(user.display_name)]));
  const companies = new Map((organizations.data ?? []).map((org) =>
    [text(org.id), text(org.display_name || org.name)]));
  return { data: { agents: (links.data ?? []).filter((link) => people.has(text(link.user_id)))
    .map((link) => ({ orgUserId: link.id, organizationName: companies.get(text(link.organization_id)) || "",
      displayName: people.get(text(link.user_id)) || "", role: link.role })) } };
}

export async function setCompanyAdmin(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  if (!context.user.is_global_admin) return { status: 403, error: "forbidden" };
  return { data: requireData(await context.db.rpc("nexstep_mobile_set_company_admin", {
    p_actor_user_id: context.user.id, p_target_org_user_id: text(payload.orgUserId),
    p_enabled: payload.enabled === true, p_audit_id: newId(),
  })) };
}
