"""Business rules for NexStep urgency colors."""

from __future__ import annotations

import datetime as dt

from utils.dates import days_between
from utils.i18n import t


URGENCY_ORDER = {"red": 0, "yellow": 1, "green": 2, "blue": 3, "gray": 4}
URGENCY_LABELS_FR = {
    "red": "Très urgent ou échue",
    "yellow": "urgent",
    "green": "Dans les temps",
    "blue": "Encore beaucoup de temps",
    "gray": "pas d'échéance",
}
URGENCY_LABELS_EN = {
    "red": "Very urgent or overdue",
    "yellow": "Urgent",
    "green": "On time",
    "blue": "Plenty of time left",
    "gray": "No due date",
}


def urgency_color(due_date: str | None, reference: dt.date | None = None) -> str:
    """Return the urgency color defined in the requirements."""

    delta = days_between(due_date, reference)
    if delta is None:
        return "gray"
    if delta < 0:
        return "red"
    if delta <= 6:
        return "yellow"
    if delta <= 30:
        return "green"
    return "blue"


def urgency_rank(due_date: str | None, reference: dt.date | None = None) -> int:
    return URGENCY_ORDER[urgency_color(due_date, reference)]


def urgency_label(color: str, language: str = "fr") -> str:
    """Return the translated business label while preserving the stored color code."""

    fallback = (URGENCY_LABELS_FR if language == "fr" else URGENCY_LABELS_EN).get(color, color)
    translated = t(f"urgency.{color}", language)
    return translated if translated != f"urgency.{color}" else fallback


def urgency_labels(language: str = "fr") -> dict[str, str]:
    return {color: urgency_label(color, language) for color in URGENCY_ORDER}
