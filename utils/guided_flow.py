"""Pure helpers for the agent-facing guided workflows.

The database deliberately keeps its historical French reference values.  The
guided interface stores short, language-neutral keys in ``st.session_state``
and translates them here only when an existing business service is called.
This keeps presentation choices out of the persistence layer.
"""

from __future__ import annotations

import datetime as dt

from utils.constants import TOUCHPOINT_TYPES
from utils.dates import today


# Values in these mappings already exist in the seeded reference tables.  They
# are not labels: the interface obtains its French and English labels from the
# locale files.
OUTCOME_VALUES = {
    "interested": "Intéressé",
    "callback": "À relancer",
    "unavailable": "Pas disponible",
    "refusal": "Refus",
}

ACTION_VALUES = {
    "call": "Appel",
    "message": "WhatsApp",
    "visit": "Visite",
    "meeting": "Rendez-vous",
    "none": None,
}

DUE_DAY_OFFSETS = {
    "today": 0,
    "tomorrow": 1,
    "3": 3,
    "7": 7,
    "14": 14,
    "30": 30,
}


def due_date_from_choice(
    choice: str,
    custom_date: dt.date | None = None,
    *,
    base_date: dt.date | None = None,
) -> str | None:
    """Return the ISO due date represented by a guided date choice."""

    if choice == "custom":
        return custom_date.isoformat() if custom_date else None
    if choice == "none":
        return None
    if choice not in DUE_DAY_OFFSETS:
        raise ValueError(f"Unknown guided due-date choice: {choice}")
    anchor = base_date or today()
    return (anchor + dt.timedelta(days=DUE_DAY_OFFSETS[choice])).isoformat()


def outcome_value(choice: str) -> str:
    """Resolve a language-neutral outcome key to the existing stored value."""

    try:
        return OUTCOME_VALUES[choice]
    except KeyError as exc:
        raise ValueError(f"Unknown guided outcome choice: {choice}") from exc


def action_value(choice: str) -> str | None:
    """Resolve a language-neutral action key to an existing action type."""

    try:
        return ACTION_VALUES[choice]
    except KeyError as exc:
        raise ValueError(f"Unknown guided action choice: {choice}") from exc


def touchpoint_value(action_type_name: str | None) -> str:
    """Use the current action type when possible, with a stable safe fallback."""

    return action_type_name if action_type_name in TOUCHPOINT_TYPES else "Autre"
