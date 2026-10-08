import { companyAgents, updateAgent } from
  "../functions/nexstep-mobile-api/_shared/agent_management.ts";
import { FakeDb } from "./fake_db.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

function fixture(): FakeDb {
  return new FakeDb({
    organization_users: [
      { id: "link-a", organization_id: "org-a", user_id: "agent-a", role: "agent",
        can_view_team: 0, is_active: 1 },
      { id: "link-b", organization_id: "org-b", user_id: "agent-b", role: "manager",
        can_view_team: 1, is_active: 0 },
    ],
    users: [
      { id: "agent-a", display_name: "Awa", email: "a@ex.test", phone: "123",
        preferred_language: "fr", is_active: 1, is_global_admin: 0 },
      { id: "agent-b", display_name: "Benoit", email: null, phone: null,
        preferred_language: "en", is_active: 0, is_global_admin: 0 },
    ],
    organizations: [{ id: "org-a", name: "Company A" }, { id: "org-b", name: "Company B" }],
  });
}

Deno.test("mobile roster includes editable agents from every company", async () => {
  const db = fixture();
  const result = await companyAgents(db.context("super_admin", true));
  const agents = (result.data as { agents: Array<Record<string, unknown>> }).agents;
  assert(agents.length === 2, "Inactive or other-company agent was omitted");
  assert(agents[1].role === "manager" && agents[1].linkActive === false,
    "The complete company role was not returned");
});

Deno.test("ordinary mobile agent cannot list or modify agents", async () => {
  const db = fixture();
  const context = db.context("agent", false);
  assert((await companyAgents(context)).status === 403, "Roster was exposed");
  assert((await updateAgent(context, {})).status === 403, "Edit was exposed");
  assert(db.calls.length === 0 && db.rpcs.length === 0, "Unauthorized data was queried");
});

Deno.test("mobile edit submits all profile and company fields to one RPC", async () => {
  const db = fixture();
  const payload = { orgUserId: "link-a", displayName: "Awa Updated",
    email: "awa@ex.test", phone: "123", language: "en", role: "company_admin",
    canViewTeam: true, accountActive: true, linkActive: true, newPin: "" };
  const result = await updateAgent(db.context("super_admin", true), payload);
  assert(result.error === undefined, "Valid agent edit failed");
  const call = db.rpcs[0];
  assert(call.name === "nexstep_mobile_update_agent", "Wrong transaction was called");
  assert(call.args.p_role === "company_admin" && call.args.p_display_name === "Awa Updated" &&
    call.args.p_target_org_user_id === "link-a", "The role or profile was dropped");
});

Deno.test("mobile edit explains a missing Supabase migration", async () => {
  const db = fixture();
  db.rpcError = { code: "PGRST202", message: "Could not find the function" };
  const result = await updateAgent(db.context("super_admin", true), {
    orgUserId: "link-a", displayName: "Awa", email: "", phone: "", language: "fr",
    role: "agent", canViewTeam: false, accountActive: true, linkActive: true, newPin: "",
  });
  assert(result.error === "mobile_migration_required", "Migration error was hidden");
});
