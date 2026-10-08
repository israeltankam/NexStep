/** Offset-paged, read-only completed actions for authorized company leaders. */

import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { text } from "./types.ts";

export const TEAM_ACTION_PAGE_SIZE = 20;
const TEAM_ROLES = new Set(["manager", "company_admin"]);

export function validTeamOffset(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) &&
    value >= 0 && value <= 1_000_000 && value % TEAM_ACTION_PAGE_SIZE === 0;
}

export async function teamActions(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  // Authentication refreshes this row for every call, so role changes take effect immediately.
  if (!TEAM_ROLES.has(text(context.orgUser.role))) {
    return { status: 403, error: "forbidden" };
  }
  const offset = payload.offset ?? 0;
  if (!validTeamOffset(offset)) return { status: 400, error: "invalid_offset" };
  const organizationId = text(context.organization.id);
  const page = await context.db.from("actions")
    .select("id,title,lead_id,completed_by_org_user_id,completed_at,completion_note")
    .eq("organization_id", organizationId).eq("status", "done")
    .not("completed_at", "is", null)
    .order("completed_at", { ascending: false }).order("id", { ascending: false })
    .range(offset, offset + TEAM_ACTION_PAGE_SIZE);
  if (page.error) throw new Error("database_error");
  const fetched = (page.data ?? []) as JsonObject[];
  const selected = fetched.slice(0, TEAM_ACTION_PAGE_SIZE);
  if (selected.length === 0) {
    return { data: { actions: [], offset, hasMore: false } };
  }

  // Join only the displayed page, never the team's entire action history.
  const leadIds = [...new Set(selected.map((row) => text(row.lead_id)).filter(Boolean))];
  const performerIds = [...new Set(selected.map((row) => text(row.completed_by_org_user_id)).filter(Boolean))];
  const [leadsResult, membersResult] = await Promise.all([
    context.db.from("leads").select("id,name").eq("organization_id", organizationId)
      .in("id", leadIds),
    performerIds.length > 0
      ? context.db.from("organization_users").select("id,user_id")
        .eq("organization_id", organizationId).in("id", performerIds)
      : Promise.resolve({ data: [], error: null }),
  ]);
  if (leadsResult.error || membersResult.error) throw new Error("database_error");
  const leads = new Map((leadsResult.data ?? []).map((lead) => [text(lead.id), text(lead.name)]));
  const members = new Map((membersResult.data ?? []).map((member) =>
    [text(member.id), text(member.user_id)]));
  const userIds = [...new Set([...members.values()])];
  const usersResult = userIds.length > 0
    ? await context.db.from("users").select("id,display_name").in("id", userIds)
    : { data: [], error: null };
  if (usersResult.error) throw new Error("database_error");
  const users = new Map((usersResult.data ?? []).map((user) =>
    [text(user.id), text(user.display_name)]));
  return { data: { offset, hasMore: fetched.length > TEAM_ACTION_PAGE_SIZE,
    actions: selected.map((action) => ({
      id: action.id, title: action.title, completedAt: action.completed_at,
      completionNote: action.completion_note || "",
      leadName: leads.get(text(action.lead_id)) || "",
      completedByName: users.get(members.get(text(action.completed_by_org_user_id)) || "") || "",
    })) } };
}
