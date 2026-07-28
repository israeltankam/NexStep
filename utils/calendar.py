"""Calendar links and ICS files for dated NexStep actions."""

from __future__ import annotations

import datetime as dt
from urllib.parse import urlencode

from utils.dates import parse_date


def _ics_escape(value: object) -> str:
    """Escape text according to RFC 5545's TEXT value rules."""

    return (
        str(value or "")
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def google_calendar_url(
    *,
    title: str,
    due_date: str,
    details: str = "",
    location: str = "",
) -> str:
    """Build Google's official prefilled event-creation URL."""

    date_value = parse_date(due_date)
    if date_value is None:
        raise ValueError("due_date_required")
    end_date = date_value + dt.timedelta(days=1)
    query = urlencode(
        {
            "action": "TEMPLATE",
            "text": title,
            "dates": f"{date_value:%Y%m%d}/{end_date:%Y%m%d}",
            "details": details,
            "location": location,
        }
    )
    return f"https://calendar.google.com/calendar/render?{query}"


def action_ics(
    *,
    action_id: str,
    title: str,
    due_date: str,
    details: str = "",
    location: str = "",
    now: dt.datetime | None = None,
) -> bytes:
    """Create an all-day event with a display reminder one day beforehand."""

    date_value = parse_date(due_date)
    if date_value is None:
        raise ValueError("due_date_required")
    end_date = date_value + dt.timedelta(days=1)
    generated = (now or dt.datetime.now(dt.UTC)).astimezone(dt.UTC)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//scale.ag//NexStep//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{_ics_escape(action_id)}@nexstep.scale-ag.tech",
        f"DTSTAMP:{generated:%Y%m%dT%H%M%SZ}",
        f"DTSTART;VALUE=DATE:{date_value:%Y%m%d}",
        f"DTEND;VALUE=DATE:{end_date:%Y%m%d}",
        f"SUMMARY:{_ics_escape(title)}",
        f"DESCRIPTION:{_ics_escape(details)}",
        f"LOCATION:{_ics_escape(location)}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_escape(title)}",
        "END:VALARM",
        "END:VEVENT",
        "END:VCALENDAR",
        "",
    ]
    return "\r\n".join(lines).encode("utf-8")
