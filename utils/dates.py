"""Date conversion and formatting utilities."""

from __future__ import annotations

import datetime as dt


ISO_DATE = "%Y-%m-%d"


def utcnow_iso() -> str:
    """Store timestamps as timezone-aware ISO strings compatible with SQLite and Postgres."""

    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def today() -> dt.date:
    return dt.date.today()


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.datetime.strptime(str(value)[:10], ISO_DATE).date()
    except ValueError:
        return None


def format_date(value: str | dt.date | None, empty: str = "—") -> str:
    parsed = parse_date(value) if not isinstance(value, dt.date) else value
    return parsed.strftime(ISO_DATE) if parsed else empty


def excel_serial_to_date(serial: int | float | str | None) -> str | None:
    """Convert dates from the standard Excel serial system used in the specification."""

    if serial in (None, ""):
        return None
    if isinstance(serial, str) and "-" in serial:
        return serial[:10]
    try:
        as_number = int(float(serial))
    except (TypeError, ValueError):
        return None
    return (dt.date(1899, 12, 30) + dt.timedelta(days=as_number)).isoformat()


def days_between(target: str | None, reference: dt.date | None = None) -> int | None:
    due = parse_date(target)
    if not due:
        return None
    anchor = reference or today()
    return (due - anchor).days
