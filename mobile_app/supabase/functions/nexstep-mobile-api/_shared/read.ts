import { canViewTeam, isAdministrator, sessionProfile } from "./auth.ts";
import { verifyStoredSecret } from "./crypto.ts";
import type { ApiResult, JsonObject, SessionContext } from "./types.ts";
import { text } from "./types.ts";

async function rows(query: PromiseLike<{ data: unknown[] | null; error: { message: string } | null }>): Promise<JsonObject[]> {
  const result = await query;
  if (result.error) throw new Error("database_error");
  return (result.data ?? []) as JsonObject[];
}

function mapBy(rowsToMap: JsonObject[], key: string): Map<string, JsonObject> {
  return new Map(rowsToMap.map((row) => [text(row[key]), row]));
}

function groupBy(rowsToGroup: JsonObject[], key: string): Map<string, JsonObject[]> {
  const grouped = new Map<string, JsonObject[]>();
  for (const row of rowsToGroup) {
    const value = text(row[key]);
    if (!grouped.has(value)) grouped.set(value, []);
    grouped.get(value)?.push(row);
  }
  return grouped;
}

function urgencyColor(dueDate: unknown): string {
  if (!dueDate) return "gray";
  const due = new Date(`${text(dueDate).slice(0, 10)}T00:00:00Z`);
  const today = new Date();
  const reference = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const delta = Math.round((due.getTime() - reference) / 86_400_000);
  if (delta < 0) return "red";
  if (delta <= 6) return "yellow";
  if (delta <= 30) return "green";
  return "blue";
}

const urgencyRank: Record<string, number> = {
  red: 0,
  yellow: 1,
  green: 2,
  blue: 3,
  gray: 4,
};

async function teamMembers(context: SessionContext): Promise<JsonObject[]> {
  const organizationId = text(context.organization.id);
  const [orgUsers, users] = await Promise.all([
    rows(context.db.from("organization_users").select(
      "id,user_id,role,can_view_team,is_active",
    ).eq("organization_id", organizationId).eq("is_active", 1).limit(2000)),
    rows(context.db.from("users").select(
      "id,display_name,email,phone,is_active",
    ).eq("is_active", 1).limit(5000)),
  ]);
  const usersById = mapBy(users, "id");
  return orgUsers
    .map((orgUser) => ({
      orgUserId: orgUser.id,
      displayName: usersById.get(text(orgUser.user_id))?.display_name || "",
      email: usersById.get(text(orgUser.user_id))?.email || "",
      phone: usersById.get(text(orgUser.user_id))?.phone || "",
      role: orgUser.role,
      canViewTeam: Boolean(orgUser.can_view_team),
    }))
    .sort((left, right) => text(left.displayName).localeCompare(text(right.displayName)));
}

async function references(context: SessionContext): Promise<JsonObject> {
  const organizationId = text(context.organization.id);
  const [stages, statuses, categories, actionTypes] = await Promise.all([
    rows(context.db.from("pipeline_stages").select("id,name,position").eq(
      "organization_id",
      organizationId,
    ).eq("is_active", 1).order("position").limit(500)),
    rows(context.db.from("lead_statuses").select("id,name,color_name,position").eq(
      "organization_id",
      organizationId,
    ).eq("is_active", 1).order("position").limit(500)),
    rows(context.db.from("client_categories").select("id,name,description").eq(
      "organization_id",
      organizationId,
    ).eq("is_active", 1).order("name").limit(500)),
    rows(context.db.from("action_types").select("id,name,position").eq(
      "organization_id",
      organizationId,
    ).eq("is_active", 1).order("position").limit(500)),
  ]);
  return { stages, statuses, categories, actionTypes };
}

export async function bootstrap(context: SessionContext): Promise<ApiResult> {
  return {
    data: {
      profile: sessionProfile(context),
      references: await references(context),
      teamMembers: canViewTeam(context) ? await teamMembers(context) : [],
      capabilities: {
        canViewTeam: canViewTeam(context),
        isAdministrator: isAdministrator(context),
        isGlobalAdmin: Boolean(context.user.is_global_admin),
      },
    },
  };
}

export async function buildLeadBoard(
  context: SessionContext,
  requestedOwnerIds: string[] | null = null,
): Promise<JsonObject[]> {
  const organizationId = text(context.organization.id);
  let ownerIds = requestedOwnerIds?.filter(Boolean) ?? null;
  if (!canViewTeam(context)) ownerIds = [text(context.orgUser.id)];

  let leadQuery = context.db.from("leads").select("*")
    .eq("organization_id", organizationId)
    .eq("is_archived", 0)
    .order("name")
    .limit(5000);
  if (ownerIds && ownerIds.length > 0) leadQuery = leadQuery.in("owner_org_user_id", ownerIds);
  const leads = await rows(leadQuery);
  if (leads.length === 0) return [];
  const leadIds = leads.map((lead) => text(lead.id));

  const [
    contacts,
    actions,
    comments,
    stageRows,
    statusRows,
    categoryRows,
    actionTypeRows,
    memberRows,
  ] = await Promise.all([
    rows(context.db.from("contacts").select("*").in("lead_id", leadIds).order(
      "created_at",
    ).limit(10000)),
    rows(context.db.from("actions").select("*").eq("organization_id", organizationId).in(
      "lead_id",
      leadIds,
    ).order("created_at", { ascending: false }).limit(10000)),
    rows(context.db.from("comments").select("*").eq("organization_id", organizationId).in(
      "lead_id",
      leadIds,
    ).order("created_at", { ascending: false }).limit(10000)),
    rows(context.db.from("pipeline_stages").select("id,name").eq(
      "organization_id",
      organizationId,
    ).limit(1000)),
    rows(context.db.from("lead_statuses").select("id,name,color_name").eq(
      "organization_id",
      organizationId,
    ).limit(1000)),
    rows(context.db.from("client_categories").select("id,name").eq(
      "organization_id",
      organizationId,
    ).limit(1000)),
    rows(context.db.from("action_types").select("id,name").eq(
      "organization_id",
      organizationId,
    ).limit(1000)),
    teamMembers(context),
  ]);

  const contactsByLead = groupBy(contacts, "lead_id");
  const actionsByLead = groupBy(actions, "lead_id");
  const commentsByLead = groupBy(comments, "lead_id");
  const stages = mapBy(stageRows, "id");
  const statuses = mapBy(statusRows, "id");
  const categories = mapBy(categoryRows, "id");
  const actionTypes = mapBy(actionTypeRows, "id");
  const members = new Map(memberRows.map((row) => [text(row.orgUserId), row]));

  return leads.map((lead) => {
    const id = text(lead.id);
    const leadContacts = contactsByLead.get(id) ?? [];
    const leadComments = commentsByLead.get(id) ?? [];
    const leadActions: JsonObject[] = (actionsByLead.get(id) ?? []).map((action): JsonObject => ({
      ...action,
      actionTypeName: actionTypes.get(text(action.action_type_id))?.name || "",
      urgencyColor: urgencyColor(action.due_date),
    }));
    const pending = leadActions
      .filter((action) => action.status === "pending")
      .sort((left, right) => {
        const rankDelta = urgencyRank[text(left.urgencyColor)] - urgencyRank[text(right.urgencyColor)];
        if (rankDelta !== 0) return rankDelta;
        return text(left.due_date || "9999-12-31").localeCompare(text(right.due_date || "9999-12-31"));
      });
    const nextAction = pending[0] ?? null;
    const contactsText = leadContacts.map((contact) => {
      const name = text(contact.full_name);
      const role = text(contact.role_title);
      const phone = text(contact.phone_raw);
      return [name, role ? `(${role})` : "", phone].filter(Boolean).join(" ");
    }).filter(Boolean).join(" | ");
    return {
      ...lead,
      stageName: stages.get(text(lead.stage_id))?.name || "",
      statusName: statuses.get(text(lead.status_id))?.name || "",
      categoryName: categories.get(text(lead.category_id))?.name || "",
      ownerName: members.get(text(lead.owner_org_user_id))?.displayName || "",
      contacts: leadContacts,
      contactsText,
      actions: leadActions,
      pendingActionCount: pending.length,
      nextAction,
      nextActionTitle: nextAction?.title || "",
      nextDueDate: nextAction?.due_date || null,
      urgencyColor: nextAction?.urgencyColor || "gray",
      comments: leadComments,
      latestComment: leadComments[0]?.body || "",
      commentCount: leadComments.length,
    };
  });
}

export async function leadBoard(
  context: SessionContext,
  payload: JsonObject,
): Promise<ApiResult> {
  const rawOwners = Array.isArray(payload.ownerIds) ? payload.ownerIds.map(text) : null;
  return { data: { leads: await buildLeadBoard(context, rawOwners) } };
}

export async function actionList(context: SessionContext): Promise<ApiResult> {
  const board = await buildLeadBoard(context, [text(context.orgUser.id)]);
  const actions: JsonObject[] = board.flatMap((lead): JsonObject[] =>
    (lead.actions as JsonObject[])
      .filter((action) =>
        action.status === "pending" &&
        text(action.assigned_to_org_user_id) === text(context.orgUser.id)
      )
      .map((action): JsonObject => ({
        ...action,
        leadName: lead.name,
        leadId: lead.id,
        contactName: (lead.contacts as JsonObject[])[0]?.full_name || "",
        phoneRaw: (lead.contacts as JsonObject[])[0]?.phone_raw || "",
        latestComment: lead.latestComment,
        contextFull: lead.context_full || "",
        obstacle: lead.obstacle || "",
      }))
  );
  actions.sort((left, right) => {
    const rankDelta = urgencyRank[text(left.urgencyColor)] - urgencyRank[text(right.urgencyColor)];
    if (rankDelta !== 0) return rankDelta;
    return text(left.due_date || "9999-12-31").localeCompare(text(right.due_date || "9999-12-31"));
  });
  return { data: { actions } };
}

export async function nextAction(context: SessionContext): Promise<ApiResult> {
  const result = await actionList(context);
  const actions = (result.data as JsonObject).actions as JsonObject[];
  return { data: { action: actions[0] ?? null } };
}

export async function pendingPasswordResets(context: SessionContext): Promise<ApiResult> {
  if (!isAdministrator(context)) return { status: 403, error: "forbidden" };
  let requestQuery = context.db.from("password_reset_requests").select("*")
    .eq("status", "pending")
    .order("requested_at")
    .limit(1000);
  if (!context.user.is_global_admin) {
    requestQuery = requestQuery.eq("organization_id", context.organization.id);
  }
  const requests = await rows(requestQuery);
  const userIds = [...new Set(requests.map((request) => text(request.user_id)))];
  const organizationIds = [
    ...new Set(requests.map((request) => text(request.organization_id))),
  ];
  const users = userIds.length
    ? await rows(context.db.from("users").select("id,display_name,email").in("id", userIds))
    : [];
  const organizations = organizationIds.length
    ? await rows(
      context.db.from("organizations").select("id,name,display_name")
        .in("id", organizationIds),
    )
    : [];
  const usersById = mapBy(users, "id");
  const organizationsById = mapBy(organizations, "id");
  return {
    data: {
      requests: requests.map((request) => ({
        ...request,
        displayName: usersById.get(text(request.user_id))?.display_name || "",
        email: usersById.get(text(request.user_id))?.email || "",
        organizationName:
          organizationsById.get(text(request.organization_id))?.display_name ||
          organizationsById.get(text(request.organization_id))?.name ||
          "",
      })),
    },
  };
}

const GLOBAL_TABLES = [
  "organizations",
  "users",
  "organization_users",
  "pipeline_stages",
  "lead_statuses",
  "client_categories",
  "action_types",
  "leads",
  "contacts",
  "actions",
  "touchpoints",
  "transfers",
  "comments",
  "import_batches",
  "import_rows",
  "auth_attempts",
  "audit_logs",
  "auth_sessions",
  "password_reset_requests",
];

const COMPANY_BUSINESS_TABLES = [
  "pipeline_stages",
  "lead_statuses",
  "client_categories",
  "action_types",
  "leads",
  "contacts",
  "actions",
  "touchpoints",
  "transfers",
  "comments",
  "import_batches",
  "import_rows",
];

export async function backup(context: SessionContext, payload: JsonObject): Promise<ApiResult> {
  if (!isAdministrator(context)) return { status: 403, error: "forbidden" };
  const global = Boolean(payload.global);
  if (global && !context.user.is_global_admin) {
    return { status: 403, error: "forbidden" };
  }
  if (
    global &&
    !await verifyStoredSecret(
      text(payload.password),
      text(context.user.password_hash),
      { normalize: false, pepper: null },
    )
  ) {
    return { status: 401, error: "invalid_credentials" };
  }

  const organizationId = text(context.organization.id);
  const companyLeads = global
    ? []
    : await rows(context.db.from("leads").select("id").eq("organization_id", organizationId));
  const leadIds = companyLeads.map((lead) => text(lead.id));
  const companyBatchIds = global
    ? []
    : (await rows(context.db.from("import_batches").select("id").eq(
      "organization_id",
      organizationId,
    ))).map((row) => text(row.id));
  const tables: JsonObject = {};

  for (const table of global ? GLOBAL_TABLES : COMPANY_BUSINESS_TABLES) {
    let query = context.db.from(table).select("*").limit(50000);
    if (!global) {
      if (table === "contacts") {
        query = leadIds.length ? query.in("lead_id", leadIds) : query.in("lead_id", ["__none__"]);
      } else if (table === "import_rows") {
        query = companyBatchIds.length
          ? query.in("import_batch_id", companyBatchIds)
          : query.in("import_batch_id", ["__none__"]);
      } else {
        query = query.eq("organization_id", organizationId);
      }
    }
    tables[table] = await rows(query);
  }
  return {
    data: {
      format: "nexstep-native-backup-v1",
      scope: global ? "global" : "organization",
      organizationId: global ? null : organizationId,
      createdAt: new Date().toISOString(),
      tables,
    },
  };
}
