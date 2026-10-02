"""Ontology-backed, explainable recommendations for one prospect at a time.

The service is deliberately advisory. It reads existing lead history, builds
semantic evidence, and returns one of the action keys already understood by
the guided interface. It never changes a lead, action, status, or churn flag.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from owlrl import DeductiveClosure, OWLRL_Semantics
from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from database.repository import fetch_all, fetch_one
from utils.dates import parse_date, today
from utils.paths import ROOT_DIR
from utils.text import normalize_name


NEX = Namespace("https://scale-ag.tech/nexstep/ontology#")
ONTOLOGY_PATH = ROOT_DIR / "ontologies" / "nexstep_sales.ttl"
RECENT_POSITIVE_DAYS = 21


@dataclass(frozen=True)
class IntelligenceEvidence:
    """Small, non-sensitive summary used to explain a recommendation."""

    completed_actions: int
    missed_deadlines: int
    negative_signals: int
    no_response_signals: int
    refusal_signals: int
    positive_signals: int
    stalled_days: int
    recent_positive: bool
    last_channel: str | None
    semantic_classes: tuple[str, ...]


@dataclass(frozen=True)
class LeadRecommendation:
    """One suggestion compatible with the existing guided action choices."""

    suggested_action: str
    suggest_churn: bool
    reason_code: str
    confidence: str
    evidence: IntelligenceEvidence


@dataclass(frozen=True)
class _Observation:
    signal_classes: frozenset[URIRef]
    occurred_on: dt.date | None


@lru_cache(maxsize=4)
def _load_ontology_version(path_text: str, modified_at_ns: int) -> Graph:
    """Parse and infer one immutable deployed version of the ontology."""

    graph = Graph()
    graph.parse(path_text, format="turtle")
    DeductiveClosure(OWLRL_Semantics).expand(graph)
    return graph


def _ontology() -> Graph:
    return _load_ontology_version(str(ONTOLOGY_PATH), ONTOLOGY_PATH.stat().st_mtime_ns)


def _local_name(value: URIRef) -> str:
    text = str(value)
    return text.rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def _date(value: object) -> dt.date | None:
    """Read both date-only fields and ISO timestamps from SQLite/PostgreSQL."""

    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    return parse_date(str(value)[:10]) if value else None


def _literal_text(graph: Graph, subject: URIRef, predicate: URIRef, default: str = "") -> str:
    value = graph.value(subject, predicate)
    return str(value) if value is not None else default


def _literal_int(graph: Graph, subject: URIRef, predicate: URIRef) -> int | None:
    value = graph.value(subject, predicate)
    return int(value) if value is not None else None


def _is_subclass(graph: Graph, candidate: URIRef, parent: URIRef) -> bool:
    return candidate == parent or (candidate, RDFS.subClassOf, parent) in graph


def _pattern_matches(normalized_text: str, raw_pattern: str) -> bool:
    """Match ontology phrases and optional ``*`` suffixes on normalized words."""

    pattern = normalize_name(raw_pattern.rstrip("*"))
    if not normalized_text or not pattern:
        return False
    if raw_pattern.endswith("*"):
        return any(word.startswith(pattern) for word in normalized_text.split())
    return f" {pattern} " in f" {normalized_text} "


def _signal_classes_for_text(graph: Graph, text: str) -> frozenset[URIRef]:
    normalized = normalize_name(text)
    matched: set[URIRef] = set()
    for signal_class, raw_pattern in graph.subject_objects(NEX.lexicalPattern):
        if not isinstance(signal_class, URIRef):
            continue
        if _pattern_matches(normalized, str(raw_pattern)):
            matched.add(signal_class)
    return frozenset(matched)


def _signal_classes_for_outcome(graph: Graph, outcome_key: str | None) -> frozenset[URIRef]:
    if not outcome_key:
        return frozenset()
    return frozenset(
        subject
        for subject in graph.subjects(NEX.outcomeKey, Literal(outcome_key))
        if isinstance(subject, URIRef)
    )


def _channel_from_text(graph: Graph, text: str) -> str | None:
    normalized = normalize_name(text)
    for action in graph.subjects(RDF.type, NEX.RecommendedAction):
        if not isinstance(action, URIRef):
            continue
        for pattern in graph.objects(action, NEX.channelPattern):
            if _pattern_matches(normalized, str(pattern)):
                return _literal_text(graph, action, NEX.actionKey) or None
    return None


def _row_text(row: Any, *columns: str) -> str:
    return " ".join(str(row[column]) for column in columns if row.get(column))


def _history_rows(conn: Any, lead_id: str) -> tuple[Any, list[Any], list[Any], list[Any]]:
    lead = fetch_one(
        conn,
        "SELECT id, churn_flag, created_at, updated_at FROM leads WHERE id = ?",
        (lead_id,),
    )
    if not lead:
        raise ValueError("Lead not found.")

    actions = fetch_all(
        conn,
        """
        SELECT a.*, at.name AS action_type_name
        FROM actions a
        LEFT JOIN action_types at ON at.id = a.action_type_id
        WHERE a.lead_id = ?
        ORDER BY a.created_at ASC
        """,
        (lead_id,),
    )
    touchpoints = fetch_all(
        conn,
        "SELECT * FROM touchpoints WHERE lead_id = ? ORDER BY occurred_at ASC",
        (lead_id,),
    )
    comments = fetch_all(
        conn,
        "SELECT * FROM comments WHERE lead_id = ? ORDER BY created_at ASC",
        (lead_id,),
    )
    # sqlite3.Row has mapping access but no ``get`` method, whereas Psycopg
    # already returns dictionaries. Normalizing here keeps all analysis code
    # identical for the local and Supabase backends.
    return (
        dict(lead),
        [dict(row) for row in actions],
        [dict(row) for row in touchpoints],
        [dict(row) for row in comments],
    )


def _observations(
    graph: Graph,
    actions: list[Any],
    touchpoints: list[Any],
    comments: list[Any],
    current_outcome_key: str | None,
    reference_date: dt.date,
) -> list[_Observation]:
    """Deduplicate notes mirrored between touchpoints and comments."""

    observations: list[_Observation] = []
    touchpoint_ids = {str(row["id"]) for row in touchpoints}
    touchpoint_action_ids = {str(row["action_id"]) for row in touchpoints if row.get("action_id")}

    for row in touchpoints:
        classes = _signal_classes_for_text(
            graph,
            _row_text(
                row,
                "outcome",
                "note",
                "decision_note",
                "action_note",
                "followup_note",
            ),
        )
        if classes:
            observations.append(_Observation(classes, _date(row.get("occurred_at"))))

    for row in comments:
        if row.get("touchpoint_id") and str(row["touchpoint_id"]) in touchpoint_ids:
            continue
        classes = _signal_classes_for_text(graph, str(row.get("body") or ""))
        if classes:
            observations.append(_Observation(classes, _date(row.get("created_at"))))

    for row in actions:
        if str(row.get("status") or "").casefold() not in {"done", "completed", "transferred"}:
            continue
        if str(row["id"]) in touchpoint_action_ids:
            continue
        classes = _signal_classes_for_text(
            graph,
            _row_text(row, "details", "completion_note"),
        )
        if classes:
            observations.append(
                _Observation(classes, _date(row.get("completed_at") or row.get("updated_at")))
            )

    projected_classes = _signal_classes_for_outcome(graph, current_outcome_key)
    if projected_classes:
        observations.append(_Observation(projected_classes, reference_date))
    return observations


def _latest_activity_date(
    lead: Any,
    actions: list[Any],
    touchpoints: list[Any],
    comments: list[Any],
) -> dt.date | None:
    values: list[object] = [lead.get("created_at")]
    for row in actions:
        values.extend((row.get("created_at"), row.get("completed_at")))
    values.extend(row.get("occurred_at") for row in touchpoints)
    values.extend(row.get("created_at") for row in comments)
    dates = [parsed for value in values if (parsed := _date(value))]
    return max(dates) if dates else None


def _last_channel(graph: Graph, actions: list[Any], touchpoints: list[Any]) -> str | None:
    candidates: list[tuple[dt.date, str]] = []
    for row in actions:
        channel = _channel_from_text(
            graph,
            _row_text(row, "action_type_name", "title"),
        )
        occurred = _date(row.get("completed_at") or row.get("created_at"))
        if channel and occurred:
            candidates.append((occurred, channel))
    for row in touchpoints:
        channel = _channel_from_text(
            graph,
            _row_text(row, "channel", "touchpoint_type"),
        )
        occurred = _date(row.get("occurred_at"))
        if channel and occurred:
            candidates.append((occurred, channel))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _build_evidence(
    graph: Graph,
    lead: Any,
    actions: list[Any],
    touchpoints: list[Any],
    comments: list[Any],
    current_outcome_key: str | None,
    reference_date: dt.date,
) -> IntelligenceEvidence:
    observations = _observations(
        graph,
        actions,
        touchpoints,
        comments,
        current_outcome_key,
        reference_date,
    )

    def count(parent: URIRef) -> int:
        return sum(
            1
            for observation in observations
            if any(_is_subclass(graph, signal_class, parent) for signal_class in observation.signal_classes)
        )

    completed = sum(
        str(row.get("status") or "").casefold() in {"done", "completed", "transferred"}
        for row in actions
    )
    if current_outcome_key:
        completed += 1

    missed_deadlines = 0
    for row in actions:
        due = _date(row.get("due_date"))
        status = str(row.get("status") or "").casefold()
        if not due:
            continue
        if status == "pending" and due < reference_date:
            missed_deadlines += 1
        elif status in {"done", "completed", "transferred"}:
            completed_on = _date(row.get("completed_at") or row.get("updated_at"))
            if completed_on and completed_on > due:
                missed_deadlines += 1

    latest_activity = _latest_activity_date(lead, actions, touchpoints, comments)
    stalled_days = max(0, (reference_date - latest_activity).days) if latest_activity else 0
    recent_positive = any(
        observation.occurred_on
        and 0 <= (reference_date - observation.occurred_on).days <= RECENT_POSITIVE_DAYS
        and any(
            _is_subclass(graph, signal_class, NEX.PositiveSignal)
            for signal_class in observation.signal_classes
        )
        for observation in observations
    )
    semantic_classes = tuple(
        sorted({_local_name(signal_class) for item in observations for signal_class in item.signal_classes})
    )
    return IntelligenceEvidence(
        completed_actions=completed,
        missed_deadlines=missed_deadlines,
        negative_signals=count(NEX.NegativeSignal),
        no_response_signals=count(NEX.NoResponseSignal),
        refusal_signals=count(NEX.RefusalSignal),
        positive_signals=count(NEX.PositiveSignal),
        stalled_days=stalled_days,
        recent_positive=recent_positive,
        last_channel=_last_channel(graph, actions, touchpoints),
        semantic_classes=semantic_classes,
    )


_POLICY_METRICS = {
    NEX.minimumCompletedActions: "completed_actions",
    NEX.minimumNegativeSignals: "negative_signals",
    NEX.minimumNoResponseSignals: "no_response_signals",
    NEX.minimumRefusalSignals: "refusal_signals",
    NEX.minimumMissedDeadlines: "missed_deadlines",
    NEX.minimumStalledDays: "stalled_days",
}


def _policy_matches(
    graph: Graph,
    policy: URIRef,
    evidence: IntelligenceEvidence,
    current_outcome_key: str | None,
) -> bool:
    trigger = _literal_text(graph, policy, NEX.triggerOutcomeKey)
    if trigger and trigger != (current_outcome_key or ""):
        return False
    last_channel = _literal_text(graph, policy, NEX.lastChannelKey)
    if last_channel and last_channel != (evidence.last_channel or ""):
        return False
    for predicate, field_name in _POLICY_METRICS.items():
        minimum = _literal_int(graph, policy, predicate)
        if minimum is not None and int(getattr(evidence, field_name)) < minimum:
            return False
    block_recent = graph.value(policy, NEX.blockWhenRecentPositive)
    if block_recent is not None and bool(block_recent.toPython()) and evidence.recent_positive:
        return False
    return True


def _ordered_policies(graph: Graph, policy_class: URIRef) -> list[URIRef]:
    policies = [
        policy
        for policy in graph.subjects(RDF.type, policy_class)
        if isinstance(policy, URIRef)
    ]
    return sorted(
        policies,
        key=lambda policy: _literal_int(graph, policy, NEX.priority) or 0,
        reverse=True,
    )


def _recommendation_from_policy(
    graph: Graph,
    policy: URIRef,
    evidence: IntelligenceEvidence,
    *,
    suggest_churn: bool,
) -> LeadRecommendation:
    action = graph.value(policy, NEX.recommendedAction)
    if not isinstance(action, URIRef):
        raise ValueError(f"Ontology policy {_local_name(policy)} has no recommended action.")
    return LeadRecommendation(
        suggested_action=_literal_text(graph, action, NEX.actionKey, "call"),
        suggest_churn=suggest_churn,
        reason_code=_literal_text(graph, policy, NEX.reasonCode, "default_followup"),
        confidence=_literal_text(graph, policy, NEX.confidence, "low"),
        evidence=evidence,
    )


def recommend_for_lead(
    conn: Any,
    lead_id: str,
    *,
    current_outcome_key: str | None = None,
    reference_date: dt.date | None = None,
) -> LeadRecommendation:
    """Return one transparent recommendation without writing to the database."""

    graph = _ontology()
    anchor = reference_date or today()
    lead, actions, touchpoints, comments = _history_rows(conn, lead_id)
    evidence = _build_evidence(
        graph,
        lead,
        actions,
        touchpoints,
        comments,
        current_outcome_key,
        anchor,
    )

    if bool(lead.get("churn_flag")):
        return LeadRecommendation(
            suggested_action="none",
            suggest_churn=True,
            reason_code="already_churn",
            confidence="high",
            evidence=evidence,
        )

    for policy in _ordered_policies(graph, NEX.ChurnPolicy):
        if _policy_matches(graph, policy, evidence, current_outcome_key):
            return _recommendation_from_policy(
                graph,
                policy,
                evidence,
                suggest_churn=True,
            )

    for policy in _ordered_policies(graph, NEX.ActionPolicy):
        if _policy_matches(graph, policy, evidence, current_outcome_key):
            return _recommendation_from_policy(
                graph,
                policy,
                evidence,
                suggest_churn=False,
            )

    raise ValueError("The ontology contains no applicable action policy.")
