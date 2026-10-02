import type { JsonObject } from "./types.ts";
import { text } from "./types.ts";

/**
 * Mobile projection of ``ontologies/nexstep_sales.ttl``.
 *
 * The Edge Function cannot import Python's RDFLib. This module therefore keeps
 * the same semantic classes, subclass inference, conservative churn policies,
 * and existing four action choices in a small dependency-free representation.
 * It is advisory only and never performs a database write.
 */

type SignalClass =
  | "PositiveSignal"
  | "NegativeSignal"
  | "EngagementSignal"
  | "InterestedSignal"
  | "CommitmentSignal"
  | "MeetingSignal"
  | "CallbackSignal"
  | "NoResponseSignal"
  | "RefusalSignal"
  | "CommercialObstacleSignal";

type ActionKey = "call" | "message" | "meeting" | "none";

export interface LeadHistory {
  lead: JsonObject;
  actions: JsonObject[];
  touchpoints: JsonObject[];
  comments: JsonObject[];
}

export interface IntelligenceEvidence {
  completedActions: number;
  missedDeadlines: number;
  negativeSignals: number;
  noResponseSignals: number;
  refusalSignals: number;
  positiveSignals: number;
  stalledDays: number;
  recentPositive: boolean;
  lastChannel: string | null;
  semanticClasses: string[];
}

export interface LeadRecommendation {
  suggestedAction: ActionKey;
  suggestChurn: boolean;
  reasonCode: string;
  confidence: "low" | "medium" | "high";
  evidence: IntelligenceEvidence;
}

interface Observation {
  classes: Set<SignalClass>;
  occurredOn: string | null;
}

interface PolicyThresholds {
  completedActions?: number;
  negativeSignals?: number;
  noResponseSignals?: number;
  refusalSignals?: number;
  missedDeadlines?: number;
  stalledDays?: number;
}

interface ChurnPolicy {
  reasonCode: string;
  confidence: "high";
  thresholds: PolicyThresholds;
}

const RECENT_POSITIVE_DAYS = 21;

const PARENTS: Partial<Record<SignalClass, SignalClass[]>> = {
  InterestedSignal: ["PositiveSignal"],
  CommitmentSignal: ["PositiveSignal"],
  MeetingSignal: ["PositiveSignal"],
  CallbackSignal: ["EngagementSignal"],
  NoResponseSignal: ["NegativeSignal"],
  RefusalSignal: ["NegativeSignal"],
  CommercialObstacleSignal: ["NegativeSignal"],
};

const PATTERNS: Partial<Record<SignalClass, string[]>> = {
  InterestedSignal: ["interesse", "interested", "interet", "interested in"],
  CommitmentSignal: [
    "accord",
    "commande",
    "devis accepte",
    "signe",
    "signed",
    "agreed",
    "order confirmed",
    "proposal accepted",
  ],
  MeetingSignal: [
    "rendez vous",
    "rdv confirme",
    "meeting confirmed",
    "appointment confirmed",
  ],
  CallbackSignal: ["a rappeler", "rappeler", "call back", "callback"],
  NoResponseSignal: [
    "pas de reponse",
    "aucune reponse",
    "sans reponse",
    "ne repond pas",
    "injoignable",
    "pas disponible",
    "no answer",
    "no response",
    "unreachable",
    "unavailable",
  ],
  RefusalSignal: [
    "refus*",
    "pas interesse",
    "non interesse",
    "ne veut pas",
    "not interested",
    "declined",
    "does not want",
  ],
  CommercialObstacleSignal: [
    "pas de budget",
    "aucun budget",
    "trop cher",
    "sans suite",
    "annul*",
    "abandon*",
    "perdu",
    "no budget",
    "too expensive",
    "cancel*",
    "lost",
  ],
};

const OUTCOME_CLASSES: Record<string, SignalClass> = {
  interested: "InterestedSignal",
  callback: "CallbackSignal",
  unavailable: "NoResponseSignal",
  refusal: "RefusalSignal",
};

const CHANNEL_PATTERNS: Record<Exclude<ActionKey, "none">, string[]> = {
  call: ["appel", "call", "phone"],
  message: ["whatsapp", "message", "sms", "email", "mail"],
  meeting: [
    "rendez vous",
    "rdv",
    "meeting",
    "visite",
    "presentation",
    "degustation",
  ],
};

const CHURN_POLICIES: ChurnPolicy[] = [
  {
    reasonCode: "repeated_refusal",
    confidence: "high",
    thresholds: { completedActions: 2, refusalSignals: 2 },
  },
  {
    reasonCode: "repeated_negative",
    confidence: "high",
    thresholds: {
      completedActions: 4,
      negativeSignals: 4,
      missedDeadlines: 2,
      stalledDays: 14,
    },
  },
  {
    reasonCode: "chronophage",
    confidence: "high",
    thresholds: {
      completedActions: 6,
      noResponseSignals: 3,
      missedDeadlines: 3,
      stalledDays: 30,
    },
  },
];

function normalize(value: unknown): string {
  return text(value)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("en")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function patternMatches(normalizedText: string, rawPattern: string): boolean {
  const stemmed = rawPattern.endsWith("*");
  const pattern = normalize(stemmed ? rawPattern.slice(0, -1) : rawPattern);
  if (!normalizedText || !pattern) return false;
  if (stemmed) {
    return normalizedText.split(" ").some((word) => word.startsWith(pattern));
  }
  return ` ${normalizedText} `.includes(` ${pattern} `);
}

function classesForText(value: unknown): Set<SignalClass> {
  const normalized = normalize(value);
  const classes = new Set<SignalClass>();
  for (const [signalClass, patterns] of Object.entries(PATTERNS)) {
    if (patterns?.some((pattern) => patternMatches(normalized, pattern))) {
      classes.add(signalClass as SignalClass);
    }
  }
  return classes;
}

function isSubclass(candidate: SignalClass, parent: SignalClass): boolean {
  if (candidate === parent) return true;
  return (PARENTS[candidate] ?? []).some((directParent) =>
    directParent === parent || isSubclass(directParent, parent)
  );
}

function isoDate(value: unknown): string | null {
  const candidate = text(value).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(candidate) ? candidate : null;
}

function daysBetween(earlier: string, later: string): number {
  const earlierMs = Date.parse(`${earlier}T00:00:00Z`);
  const laterMs = Date.parse(`${later}T00:00:00Z`);
  return Math.max(0, Math.round((laterMs - earlierMs) / 86_400_000));
}

function rowText(row: JsonObject, keys: string[]): string {
  return keys.map((key) => text(row[key])).filter(Boolean).join(" ");
}

function observations(
  history: LeadHistory,
  currentOutcomeKey: string,
  referenceDate: string,
): Observation[] {
  const result: Observation[] = [];
  const touchpointIds = new Set(history.touchpoints.map((row) => text(row.id)));
  const touchpointActionIds = new Set(
    history.touchpoints.map((row) => text(row.action_id)).filter(Boolean),
  );

  for (const row of history.touchpoints) {
    const classes = classesForText(rowText(row, [
      "outcome",
      "note",
      "decision_note",
      "action_note",
      "followup_note",
    ]));
    if (classes.size) {
      result.push({ classes, occurredOn: isoDate(row.occurred_at) });
    }
  }
  for (const row of history.comments) {
    if (row.touchpoint_id && touchpointIds.has(text(row.touchpoint_id))) {
      continue;
    }
    const classes = classesForText(row.body);
    if (classes.size) {
      result.push({ classes, occurredOn: isoDate(row.created_at) });
    }
  }
  for (const row of history.actions) {
    if (
      !["done", "completed", "transferred"].includes(
        text(row.status).toLowerCase(),
      )
    ) continue;
    if (touchpointActionIds.has(text(row.id))) continue;
    const classes = classesForText(
      rowText(row, ["details", "completion_note"]),
    );
    if (classes.size) {
      result.push({
        classes,
        occurredOn: isoDate(row.completed_at || row.updated_at),
      });
    }
  }
  const projectedClass = OUTCOME_CLASSES[currentOutcomeKey];
  if (projectedClass) {
    result.push({
      classes: new Set([projectedClass]),
      occurredOn: referenceDate,
    });
  }
  return result;
}

function channelFromText(value: unknown): string | null {
  const normalized = normalize(value);
  for (const [channel, patterns] of Object.entries(CHANNEL_PATTERNS)) {
    if (patterns.some((pattern) => patternMatches(normalized, pattern))) {
      return channel;
    }
  }
  return null;
}

function latestChannel(history: LeadHistory): string | null {
  const candidates: Array<{ date: string; channel: string }> = [];
  for (const row of history.actions) {
    const channel = channelFromText(rowText(row, ["actionTypeName", "title"]));
    const date = isoDate(row.completed_at || row.created_at);
    if (channel && date) candidates.push({ date, channel });
  }
  for (const row of history.touchpoints) {
    const channel = channelFromText(
      rowText(row, ["channel", "touchpoint_type"]),
    );
    const date = isoDate(row.occurred_at);
    if (channel && date) candidates.push({ date, channel });
  }
  candidates.sort((left, right) => right.date.localeCompare(left.date));
  return candidates[0]?.channel ?? null;
}

function evidence(
  history: LeadHistory,
  currentOutcomeKey: string,
  referenceDate: string,
): IntelligenceEvidence {
  const observed = observations(history, currentOutcomeKey, referenceDate);
  const count = (parent: SignalClass): number =>
    observed.filter((observation) =>
      [...observation.classes].some((candidate) =>
        isSubclass(candidate, parent)
      )
    ).length;

  let completedActions =
    history.actions.filter((action) =>
      ["done", "completed", "transferred"].includes(
        text(action.status).toLowerCase(),
      )
    ).length;
  if (currentOutcomeKey) completedActions += 1;

  let missedDeadlines = 0;
  for (const action of history.actions) {
    const due = isoDate(action.due_date);
    if (!due) continue;
    const status = text(action.status).toLowerCase();
    if (status === "pending" && due < referenceDate) {
      missedDeadlines += 1;
      continue;
    }
    if (["done", "completed", "transferred"].includes(status)) {
      const completedOn = isoDate(action.completed_at || action.updated_at);
      if (completedOn && completedOn > due) missedDeadlines += 1;
    }
  }

  const activityDates = [
    isoDate(history.lead.created_at),
    ...history.actions.flatMap((
      row,
    ) => [isoDate(row.created_at), isoDate(row.completed_at)]),
    ...history.touchpoints.map((row) => isoDate(row.occurred_at)),
    ...history.comments.map((row) => isoDate(row.created_at)),
  ].filter((value): value is string => Boolean(value));
  activityDates.sort((left, right) => right.localeCompare(left));
  const stalledDays = activityDates[0]
    ? daysBetween(activityDates[0], referenceDate)
    : 0;

  const recentPositive = observed.some((observation) =>
    observation.occurredOn !== null &&
    observation.occurredOn <= referenceDate &&
    daysBetween(observation.occurredOn, referenceDate) <=
      RECENT_POSITIVE_DAYS &&
    [...observation.classes].some((candidate) =>
      isSubclass(candidate, "PositiveSignal")
    )
  );

  return {
    completedActions,
    missedDeadlines,
    negativeSignals: count("NegativeSignal"),
    noResponseSignals: count("NoResponseSignal"),
    refusalSignals: count("RefusalSignal"),
    positiveSignals: count("PositiveSignal"),
    stalledDays,
    recentPositive,
    lastChannel: latestChannel(history),
    semanticClasses: [...new Set(observed.flatMap((item) => [...item.classes]))]
      .sort(),
  };
}

function policyMatches(
  policy: ChurnPolicy,
  facts: IntelligenceEvidence,
): boolean {
  if (facts.recentPositive) return false;
  return Object.entries(policy.thresholds).every(([field, minimum]) =>
    Number(facts[field as keyof IntelligenceEvidence]) >= Number(minimum)
  );
}

export function recommendLead(
  history: LeadHistory,
  currentOutcomeKey = "",
  referenceDate = new Date().toISOString().slice(0, 10),
): LeadRecommendation {
  const facts = evidence(history, currentOutcomeKey, referenceDate);
  const alreadyChurn = history.lead.churn_flag === true ||
    Number(history.lead.churn_flag) === 1;
  if (alreadyChurn) {
    return {
      suggestedAction: "none",
      suggestChurn: true,
      reasonCode: "already_churn",
      confidence: "high",
      evidence: facts,
    };
  }
  for (const policy of CHURN_POLICIES) {
    if (policyMatches(policy, facts)) {
      return {
        suggestedAction: "none",
        suggestChurn: true,
        reasonCode: policy.reasonCode,
        confidence: policy.confidence,
        evidence: facts,
      };
    }
  }

  if (currentOutcomeKey === "interested") {
    return actionRecommendation("meeting", "recent_interest", "high", facts);
  }
  if (currentOutcomeKey === "callback") {
    return actionRecommendation("call", "callback_requested", "high", facts);
  }
  if (currentOutcomeKey === "refusal") {
    return actionRecommendation("none", "latest_refusal", "medium", facts);
  }
  if (currentOutcomeKey === "unavailable" && facts.noResponseSignals >= 2) {
    return actionRecommendation(
      "message",
      "repeated_no_response",
      "high",
      facts,
    );
  }
  if (facts.lastChannel === "call") {
    return actionRecommendation(
      "message",
      "alternate_after_call",
      "medium",
      facts,
    );
  }
  if (facts.lastChannel === "message") {
    return actionRecommendation(
      "call",
      "alternate_after_message",
      "medium",
      facts,
    );
  }
  return actionRecommendation("call", "default_followup", "low", facts);
}

function actionRecommendation(
  suggestedAction: ActionKey,
  reasonCode: string,
  confidence: "low" | "medium" | "high",
  facts: IntelligenceEvidence,
): LeadRecommendation {
  return {
    suggestedAction,
    suggestChurn: false,
    reasonCode,
    confidence,
    evidence: facts,
  };
}
