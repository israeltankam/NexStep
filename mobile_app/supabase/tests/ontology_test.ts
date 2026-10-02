import {
  type LeadHistory,
  recommendLead,
} from "../functions/nexstep-mobile-api/_shared/ontology.ts";

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(message);
}

function chronophageHistory(): LeadHistory {
  const actions = Array.from({ length: 6 }, (_, index) => ({
    id: `action-${index}`,
    status: "done",
    title: "Appel",
    actionTypeName: "Appel",
    due_date: "2026-01-01",
    created_at: "2026-01-01T00:00:00+00:00",
    completed_at: "2026-02-01T00:00:00+00:00",
    updated_at: "2026-02-01T00:00:00+00:00",
  }));
  const touchpoints = actions.map((action, index) => ({
    id: `touchpoint-${index}`,
    action_id: action.id,
    outcome: "Pas disponible",
    note: "Aucune réponse, contact injoignable.",
    touchpoint_type: "Appel",
    occurred_at: "2026-02-01T00:00:00+00:00",
  }));
  return {
    lead: {
      id: "lead-1",
      churn_flag: 0,
      created_at: "2026-01-01T00:00:00+00:00",
    },
    actions,
    touchpoints,
    comments: touchpoints.map((touchpoint, index) => ({
      id: `comment-${index}`,
      touchpoint_id: touchpoint.id,
      body: "Aucune réponse, contact injoignable.",
      created_at: "2026-02-01T00:00:00+00:00",
    })),
  };
}

Deno.test("mobile ontology suggests churn for a chronophage history", () => {
  const recommendation = recommendLead(
    chronophageHistory(),
    "unavailable",
    "2026-08-11",
  );
  assert(recommendation.suggestChurn, "Churn should be suggested");
  assert(recommendation.suggestedAction === "none", "Follow-up should stop");
  assert(
    recommendation.evidence.semanticClasses.includes("NoResponseSignal"),
    "No-response evidence was not inferred",
  );
});

Deno.test("linked comments are not counted twice", () => {
  const recommendation = recommendLead(
    chronophageHistory(),
    "",
    "2026-08-11",
  );
  assert(
    recommendation.evidence.noResponseSignals === 6,
    "Touchpoint comments were double counted",
  );
});

Deno.test("a recent positive signal blocks churn", () => {
  const recommendation = recommendLead(
    chronophageHistory(),
    "interested",
    "2026-08-11",
  );
  assert(!recommendation.suggestChurn, "Recent interest must block churn");
  assert(
    recommendation.suggestedAction === "meeting",
    "Interest should suggest a meeting",
  );
});

Deno.test("a callback request suggests a call", () => {
  const history: LeadHistory = {
    lead: { id: "lead-2", churn_flag: 0, created_at: "2026-08-10" },
    actions: [],
    touchpoints: [],
    comments: [],
  };
  const recommendation = recommendLead(history, "callback", "2026-08-11");
  assert(!recommendation.suggestChurn, "A callback is not churn");
  assert(
    recommendation.suggestedAction === "call",
    "A callback should suggest a call",
  );
});

Deno.test("an existing churn flag remains advisory and read-only", () => {
  const history: LeadHistory = {
    lead: { id: "lead-3", churn_flag: 1, created_at: "2026-08-10" },
    actions: [],
    touchpoints: [],
    comments: [],
  };
  const serializedBefore = JSON.stringify(history);
  const recommendation = recommendLead(history, "callback", "2026-08-11");
  assert(recommendation.suggestChurn, "Existing churn was ignored");
  assert(
    JSON.stringify(history) === serializedBefore,
    "Recommendation mutated its input",
  );
});
