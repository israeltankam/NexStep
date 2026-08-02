import type { SupabaseClient } from "npm:@supabase/supabase-js@2";

import { hashPassword, hmacHex, normalizePin, randomToken, verifyStoredSecret } from "./crypto.ts";
import { pinPepper, requireData } from "./client.ts";
import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { newId, nowIso, text } from "./types.ts";

const SESSION_DAYS = 30;

function profile(organization: JsonObject, user: JsonObject, orgUser: JsonObject): JsonObject {
  return {
    organizationId: organization.id,
    organizationName: organization.display_name || organization.name,
    organizationSlug: organization.slug,
    userId: user.id,
    displayName: user.display_name,
    orgUserId: orgUser.id,
    role: orgUser.role,
    canViewTeam: Boolean(orgUser.can_view_team),
    isGlobalAdmin: Boolean(user.is_global_admin),
    language: user.preferred_language || organization.default_language || "fr",
  };
}

async function logAttempt(
  db: SupabaseClient,
  organizationLookup: string,
  agentLookup: string,
  success: boolean,
  reason: string | null,
  request: Request,
): Promise<void> {
  await db.from("auth_attempts").insert({
    id: newId(),
    organization_lookup: organizationLookup,
    agent_lookup: agentLookup,
    success: success ? 1 : 0,
    failure_reason: reason,
    ip_address: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || null,
    user_agent: request.headers.get("user-agent"),
    created_at: nowIso(),
  });
}

async function identify(
  db: SupabaseClient,
  companyPin: string,
  agentPin: string,
  request: Request,
): Promise<{ organization: JsonObject; user: JsonObject; orgUser: JsonObject } | null> {
  const pepper = pinPepper();
  const companyLookup = await hmacHex(pepper, normalizePin(companyPin));
  const agentLookup = await hmacHex(pepper, normalizePin(agentPin));
  const cutoff = new Date(Date.now() - 15 * 60 * 1000).toISOString();
  const failures = await db
    .from("auth_attempts")
    .select("id", { count: "exact", head: true })
    .eq("organization_lookup", companyLookup)
    .eq("agent_lookup", agentLookup)
    .eq("success", 0)
    .gte("created_at", cutoff);
  if ((failures.count ?? 0) >= 5) {
    await logAttempt(db, companyLookup, agentLookup, false, "too_many_attempts", request);
    throw new Error("too_many_attempts");
  }

  const organizationResult = await db
    .from("organizations")
    .select("*")
    .eq("company_pin_lookup", companyLookup)
    .eq("is_active", 1)
    .maybeSingle();
  const organization = organizationResult.data as JsonObject | null;
  const validCompany = organization && await verifyStoredSecret(
    companyPin,
    text(organization.company_pin_hash),
    { normalize: true, pepper },
  );
  if (!validCompany) {
    await logAttempt(db, companyLookup, agentLookup, false, "invalid_credentials", request);
    return null;
  }

  const orgUserResult = await db
    .from("organization_users")
    .select("*")
    .eq("organization_id", organization.id)
    .eq("agent_pin_lookup", agentLookup)
    .eq("is_active", 1)
    .maybeSingle();
  const orgUser = orgUserResult.data as JsonObject | null;
  const validAgent = orgUser && await verifyStoredSecret(
    agentPin,
    text(orgUser.agent_pin_hash),
    { normalize: true, pepper },
  );
  if (!validAgent) {
    await logAttempt(db, companyLookup, agentLookup, false, "invalid_credentials", request);
    return null;
  }

  const userResult = await db
    .from("users")
    .select("*")
    .eq("id", orgUser.user_id)
    .eq("is_active", 1)
    .maybeSingle();
  const user = userResult.data as JsonObject | null;
  if (!user) {
    await logAttempt(db, companyLookup, agentLookup, false, "invalid_credentials", request);
    return null;
  }
  return { organization, user, orgUser };
}

async function createSession(
  db: SupabaseClient,
  organization: JsonObject,
  user: JsonObject,
  orgUser: JsonObject,
): Promise<JsonObject> {
  const sessionId = newId();
  const token = randomToken();
  const tokenHash = await hmacHex(pinPepper(), token);
  const expiresAt = new Date(Date.now() + SESSION_DAYS * 86_400_000).toISOString();
  requireData(await db.from("auth_sessions").insert({
    id: sessionId,
    organization_id: organization.id,
    user_id: user.id,
    org_user_id: orgUser.id,
    token_hash: tokenHash,
    expires_at: expiresAt,
    created_at: nowIso(),
    last_used_at: null,
    revoked_at: null,
  }).select("id").single());
  return {
    accessToken: `${sessionId}.${token}`,
    expiresAt,
    profile: profile(organization, user, orgUser),
  };
}

/**
 * Reproduce Streamlit's first login step: validate both PINs, then tell the
 * native client which password form to display without exposing account data.
 */
export async function identifyLogin(
  db: SupabaseClient,
  payload: JsonObject,
  request: Request,
): Promise<ApiResult> {
  const identified = await identify(
    db,
    text(payload.companyPin),
    text(payload.agentPin),
    request,
  );
  if (!identified) return { status: 401, error: "invalid_credentials" };

  const { organization, user, orgUser } = identified;
  await logAttempt(
    db,
    text(organization.company_pin_lookup),
    text(orgUser.agent_pin_lookup),
    true,
    null,
    request,
  );
  return {
    data: {
      displayName: text(user.display_name),
      passwordMode: !text(user.password_hash)
        ? "setup"
        : user.must_change_password
        ? "change"
        : "login",
    },
  };
}

export async function login(
  db: SupabaseClient,
  payload: JsonObject,
  request: Request,
): Promise<ApiResult> {
  const companyPin = text(payload.companyPin);
  const agentPin = text(payload.agentPin);
  const password = text(payload.password);
  const newPassword = text(payload.newPassword);
  const identified = await identify(db, companyPin, agentPin, request);
  if (!identified) return { status: 401, error: "invalid_credentials" };

  const { organization, user, orgUser } = identified;
  const passwordHash = text(user.password_hash);
  if (!passwordHash) {
    if (!newPassword) return { status: 409, error: "password_setup_required" };
    if (newPassword.length < 4) return { status: 400, error: "password_too_short" };
    const updated = requireData(await db.from("users").update({
      password_hash: await hashPassword(newPassword),
      password_set_at: nowIso(),
      must_change_password: 0,
      updated_at: nowIso(),
    }).eq("id", user.id).select("*").single()) as JsonObject;
    await logAttempt(db, text(organization.company_pin_lookup), text(orgUser.agent_pin_lookup), true, null, request);
    return { data: await createSession(db, organization, updated, orgUser) };
  }

  if (!await verifyStoredSecret(password, passwordHash, { normalize: false, pepper: null })) {
    await logAttempt(
      db,
      text(organization.company_pin_lookup),
      text(orgUser.agent_pin_lookup),
      false,
      "invalid_password",
      request,
    );
    return { status: 401, error: "invalid_credentials" };
  }

  if (user.must_change_password) {
    if (!newPassword) return { status: 409, error: "password_change_required" };
    if (newPassword.length < 4) return { status: 400, error: "password_too_short" };
    Object.assign(user, requireData(await db.from("users").update({
      password_hash: await hashPassword(newPassword),
      password_set_at: nowIso(),
      must_change_password: 0,
      updated_at: nowIso(),
    }).eq("id", user.id).select("*").single()));
  }

  await logAttempt(db, text(organization.company_pin_lookup), text(orgUser.agent_pin_lookup), true, null, request);
  return { data: await createSession(db, organization, user, orgUser) };
}

export async function requestPasswordReset(
  db: SupabaseClient,
  payload: JsonObject,
  request: Request,
): Promise<ApiResult> {
  const identified = await identify(
    db,
    text(payload.companyPin),
    text(payload.agentPin),
    request,
  );
  if (!identified) return { status: 401, error: "invalid_credentials" };
  const { organization, user, orgUser } = identified;
  const existing = await db
    .from("password_reset_requests")
    .select("id")
    .eq("organization_id", organization.id)
    .eq("user_id", user.id)
    .eq("status", "pending")
    .maybeSingle();
  if (existing.data) return { data: { requestId: existing.data.id } };

  const requestId = newId();
  requireData(await db.from("password_reset_requests").insert({
    id: requestId,
    organization_id: organization.id,
    user_id: user.id,
    org_user_id: orgUser.id,
    status: "pending",
    requested_at: nowIso(),
  }).select("id").single());
  return { data: { requestId } };
}

export async function authenticate(
  db: SupabaseClient,
  request: Request,
): Promise<SessionContext | null> {
  const authorization = request.headers.get("authorization") || "";
  const supplied = authorization.startsWith("Bearer ") ? authorization.slice(7).trim() : "";
  const separator = supplied.indexOf(".");
  if (separator < 1) return null;
  const sessionId = supplied.slice(0, separator);
  const token = supplied.slice(separator + 1);
  const tokenHash = await hmacHex(pinPepper(), token);
  const sessionResult = await db
    .from("auth_sessions")
    .select("*")
    .eq("id", sessionId)
    .eq("token_hash", tokenHash)
    .is("revoked_at", null)
    .maybeSingle();
  const session = sessionResult.data as JsonObject | null;
  if (!session || Date.parse(text(session.expires_at)) <= Date.now()) return null;

  const [organizationResult, userResult, orgUserResult] = await Promise.all([
    db.from("organizations").select("*").eq("id", session.organization_id).eq("is_active", 1).maybeSingle(),
    db.from("users").select("*").eq("id", session.user_id).eq("is_active", 1).maybeSingle(),
    db.from("organization_users").select("*").eq("id", session.org_user_id).eq("is_active", 1).maybeSingle(),
  ]);
  if (!organizationResult.data || !userResult.data || !orgUserResult.data) return null;
  await db.from("auth_sessions").update({ last_used_at: nowIso() }).eq("id", sessionId);
  return {
    db,
    sessionId,
    organization: organizationResult.data as JsonObject,
    user: userResult.data as JsonObject,
    orgUser: orgUserResult.data as JsonObject,
  };
}

export function sessionProfile(context: SessionContext): JsonObject {
  return profile(context.organization, context.user, context.orgUser);
}

export function canViewTeam(context: SessionContext): boolean {
  return Boolean(context.orgUser.can_view_team) ||
    ["manager", "company_admin", "super_admin"].includes(text(context.orgUser.role)) ||
    Boolean(context.user.is_global_admin);
}

export function isAdministrator(context: SessionContext): boolean {
  return ["company_admin", "super_admin"].includes(text(context.orgUser.role)) ||
    Boolean(context.user.is_global_admin);
}
