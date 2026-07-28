"""Reusable Streamlit controls for adding an action to a calendar."""

from __future__ import annotations

import streamlit as st

from utils.calendar import action_ics, google_calendar_url
from utils.i18n import t
from utils.text import slugify


def render_calendar_tools(
    action: dict[str, object],
    language: str,
    *,
    lead_name: str = "",
    location: str = "",
    key_prefix: str = "calendar",
) -> None:
    """Show Google and ICS choices only when the action has a due date."""

    due_date = str(action.get("due_date") or "")
    if not due_date:
        st.caption(t("calendar.no_due_date", language))
        return

    title = f"{lead_name} - {action.get('title') or ''}".strip(" -")
    details = str(action.get("details") or "")
    google_url = google_calendar_url(
        title=title,
        due_date=due_date,
        details=details,
        location=location,
    )
    calendar_file = action_ics(
        action_id=str(action.get("id") or "nexstep-action"),
        title=title,
        due_date=due_date,
        details=details,
        location=location,
    )

    col_google, col_ics = st.columns(2)
    col_google.link_button(
        t("calendar.google", language),
        google_url,
        use_container_width=True,
    )
    col_ics.download_button(
        t("calendar.ics", language),
        calendar_file,
        file_name=f"{slugify(title) or key_prefix}.ics",
        mime="text/calendar",
        key=f"{key_prefix}_ics_{action.get('id')}",
        use_container_width=True,
    )
    st.caption(t("calendar.reminder", language))
