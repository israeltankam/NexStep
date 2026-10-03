/** Global-admin agent roster and atomic profile/company-permission updates. */

import { hashPassword, hmacHex, normalizePin } from "./crypto.ts";
import { pinPepper, requireData } from "./client.ts";
import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { newId, text } from "./types.ts";

const ROLES = ["agent", "manager", "company_admin"];

export async function companyAgents(context: SessionContext): Promise<ApiResult> {
  if (!context.user.is_global_admin) return { status: 403, error: "forbidden" };
  const [links, users, organizations] = await Promise.all([
    context.db.from("organization_users")
      .select("id,organization_id,user_id,role,can_view_team,is_active")
      .in("role", ROLES).limit(5000),
    context.db.from("users")
      .select("id,display_name,email,phone,preferred_language,is_active,is_global_admin")
      .eq("is_global_admin", 0).limit(5000),
    context.db.from("organizations").select("id,name,display_name").limit(1000),
  ]);
  if (links.error || users.error || organizations.error) throw new Error("database_error");
  const people = new Map((users.data ?? []).map((user) => [text(user.id), user]));
  const companies = new Map((organizations.data ?? []).map((org) =>
    [text(org.id), text(org.display_name || org.name)]));
  return { data: { agents: (links.data ?? []).filter((link) => people.has(text(link.user_id)))
    .map((link) => {
      const person = people.get(text(link.user_id))!;
      return { orgUserId: link.id, organizationName: companies.get(text(link.organization_id)) || "",
        displayName: person.display_name, email: person.email || "", phone: person.phone || "",
        language: person.preferred_language || "fr", role: link.role,
        canViewTeam: Boolean(link.can_view_team), linkActive: Boolean(link.is_active),
        accountActive: Boolean(person.is_active) };
    }) } };
}

export async function updateAgent(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  if (!context.user.is_global_admin) return { status: 403, error: "forbidden" };
  const name = text(payload.displayName).trim();
  const email = text(payload.email).trim().toLowerCase();
  const phone = text(payload.phone).trim();
  const language = text(payload.language);
  const role = text(payload.role);
  const pin = text(payload.newPin);
  if (!text(payload.orgUserId) || !name || name.length > 200 || email.length > 254 ||
      phone.length > 80 || (email && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) ||
      !["fr", "en"].includes(language) || !ROLES.includes(role) ||
      typeof payload.accountActive !== "boolean" || typeof payload.linkActive !== "boolean" ||
      typeof payload.canViewTeam !== "boolean" || pin.length > 128 ||
      (pin && !normalizePin(pin))) {
    return { status: 400, error: "invalid_agent_details" };
  }
  // PIN lookup matches Python's HMAC; the verifier uses PBKDF2 of normalized PIN + pepper.
  const pepper = pin ? pinPepper() : "";
  const lookup = pin ? await hmacHex(pepper, normalizePin(pin)) : null;
  const pinHash = pin ? await hashPassword(normalizePin(pin) + pepper) : null;
  const result = await context.db.rpc("nexstep_mobile_update_agent", {
    p_actor_user_id: context.user.id, p_target_org_user_id: text(payload.orgUserId),
    p_display_name: name, p_email: email || null, p_phone: phone || null,
    p_preferred_language: language, p_role: role,
    p_can_view_team: payload.canViewTeam, p_account_active: payload.accountActive,
    p_link_active: payload.linkActive, p_agent_pin_lookup: lookup,
    p_agent_pin_hash: pinHash, p_audit_id: newId(),
  });
  if (result.error) {
    // PostgreSQL supplies the exact validation code; expose only known messages.
    const message = result.error.message;
    for (const code of ["forbidden", "invalid_agent", "invalid_agent_details", "duplicate_pin"]) {
      if (message.includes(code)) return { status: code === "forbidden" ? 403 : 400, error: code };
    }
    throw new Error("database_error");
  }
  return { data: requireData(result) };
}

/** Keep the previous APK's narrow promotion operation usable during rollout. */
export async function setCompanyAdmin(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  if (!context.user.is_global_admin) return { status: 403, error: "forbidden" };
  return { data: requireData(await context.db.rpc("nexstep_mobile_set_company_admin", {
    p_actor_user_id: context.user.id, p_target_org_user_id: text(payload.orgUserId),
    p_enabled: payload.enabled === true, p_audit_id: newId(),
  })) };
}
