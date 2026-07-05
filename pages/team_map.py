"""Operational team map: counts, overdue actions, and expandable comments."""

from __future__ import annotations

import sqlite3

import streamlit as st

from services.lead_service import team_summary, unassigned_leads_count
from utils.i18n import t
from utils.text import truncate
from utils.ui import render_comments, urgency_badge
from utils.urgency import urgency_label, urgency_labels


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    st.title("🗺️ " + t("team.title", language))
    summaries = team_summary(conn, str(session["organization_id"]))
    unassigned = unassigned_leads_count(conn, str(session["organization_id"]))
    st.metric(t("team.unassigned", language), unassigned)

    if not summaries:
        st.info(t("team.empty", language))
        return

    for summary in summaries:
        agent = summary["agent"]
        urgencies = summary["urgencies"]
        labels = urgency_labels(language)
        st.markdown(f"### {agent['display_name']}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(labels["red"], urgencies["red"])
        c2.metric(labels["yellow"], urgencies["yellow"])
        c3.metric(labels["green"], urgencies["green"])
        c4.metric(labels["blue"], urgencies["blue"])
        c5.metric(labels["gray"], urgencies["gray"])
        with st.expander(t("team.expand", language)):
            for action in summary["actions"][:12]:
                color = action["urgency_color_cache"] or "gray"
                st.markdown(
                    f"{urgency_badge(color, urgency_label(color, language))} **{action['lead_name']}** · {action['title']} · {action['due_date'] or '—'}",
                    unsafe_allow_html=True,
                )
            if summary["recent_comments"]:
                st.caption(t("comments.latest", language))
                render_comments(summary["recent_comments"], max_preview=180)
            else:
                st.caption(t("comments.none", language))
            blocked = [action for action in summary["actions"] if "blo" in truncate(str(action["details"] or ""), 80).casefold()]
            if blocked:
                st.warning(t("team.blocked_hint", language, count=len(blocked)))
