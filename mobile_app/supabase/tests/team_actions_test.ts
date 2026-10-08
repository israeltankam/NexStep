import { teamActions, validTeamOffset } from
  "../functions/nexstep-mobile-api/_shared/team_actions.ts";
import { FakeDb } from "./fake_db.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

function fixture(): FakeDb {
  const actions = Array.from({ length: 25 }, (_, index) => ({
    id: `action-${String(index).padStart(2, "0")}`, organization_id: "org-a",
    status: "done", lead_id: "lead-a", completed_by_org_user_id: "member-a",
    title: `Call ${index}`, completion_note: "Completed",
    completed_at: `2026-10-08T12:${String(index).padStart(2, "0")}:00Z`,
  }));
  actions.push({ ...actions[0], id: "foreign-action", organization_id: "org-b" });
  actions.push({ ...actions[0], id: "pending-action", status: "pending" });
  return new FakeDb({ actions, leads: [
    { id: "lead-a", organization_id: "org-a", name: "Prospect A" },
    { id: "lead-b", organization_id: "org-b", name: "Prospect B" },
  ], organization_users: [{ id: "member-a", organization_id: "org-a", user_id: "user-a" }],
  users: [{ id: "user-a", display_name: "Awa" }] });
}

Deno.test("manager sees only a 20-action page in newest-first order", async () => {
  const db = fixture();
  const result = await teamActions(db.context("manager"), { offset: 0 });
  const data = result.data as { actions: Array<Record<string, unknown>>; hasMore: boolean };
  assert(data.actions.length === 20 && data.hasMore, "The first page is unbounded");
  assert(data.actions[0].title === "Call 24", "Newest action is not first");
  assert(data.actions[0].completedByName === "Awa", "Performer was not resolved");
  assert(db.calls.find((call) => call.table === "actions")?.range?.join(",") === "0,20",
    "The database query did not use offset pagination with one lookahead row");
  assert(db.calls.filter((call) => ["actions", "leads", "organization_users"].includes(call.table))
    .every((call) => call.filters.some(([column, value]) =>
      column === "organization_id" && value === "org-a")), "A query escaped the company");
});

Deno.test("second mobile page has five actions and no next page", async () => {
  const db = fixture();
  const result = await teamActions(db.context("company_admin"), { offset: 20 });
  const data = result.data as { actions: Array<Record<string, unknown>>; hasMore: boolean };
  assert(data.actions.length === 5 && !data.hasMore, "Second page is incorrect");
  assert(data.actions[0].title === "Call 4", "Offset did not skip the first page");
});

Deno.test("ordinary agent cannot read team actions even with a visibility flag", async () => {
  const db = fixture();
  const context = db.context("agent");
  context.orgUser.can_view_team = 1;
  const result = await teamActions(context, { offset: 0 });
  assert(result.status === 403 && db.calls.length === 0, "Unauthorized data was queried");
});

Deno.test("invalid offsets are refused before querying", async () => {
  for (const offset of [-20, 1, "20", 1_000_020]) {
    const db = fixture();
    const result = await teamActions(db.context("manager"), { offset });
    assert(result.error === "invalid_offset" && db.calls.length === 0,
      "An invalid offset reached the database");
  }
  assert(validTeamOffset(40), "A valid page boundary was refused");
});
