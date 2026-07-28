"""List and filter all actions assigned to the current agent."""

from __future__ import annotations

import sqlite3

import streamlit as st

from components.calendar_tools import render_calendar_tools
from services.action_service import list_actions
from services.comment_service import add_comment
from utils.i18n import t
from utils.text import truncate
from utils.ui import urgency_badge
from utils.urgency import urgency_labels


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    st.title("✅ " + t("actions.title", language))
    actions = list_actions(conn, str(session["organization_id"]), org_user_id=str(session["org_user_id"]))
    if not actions:
        st.success(t("actions.empty", language))
        return

    labels = urgency_labels(language)
    label_to_color = {label: color for color, label in labels.items()}
    filter_labels = list(label_to_color)
    urgency_filter = st.multiselect(
        t("actions.filter_urgency", language),
        filter_labels,
        default=filter_labels,
        key="urgency_filter_labels_v2",
    )
    selected_colors = {label_to_color[label] for label in urgency_filter}
    search = st.text_input(t("actions.filter_client", language))
    filtered = [
        action
        for action in actions
        if action["urgency_color"] in selected_colors and search.casefold() in str(action["lead_name"]).casefold()
    ]
    st.caption(t("actions.count", language, count=len(filtered)))

    for action in filtered:
        with st.expander(f"{labels[action['urgency_color']]} · {action['lead_name']} · {action['title']}", expanded=action["urgency_color"] == "red"):
            st.markdown(
                f"{urgency_badge(action['urgency_color'], labels[action['urgency_color']])} "
                f"**{action['title']}** · {action['due_date'] or '—'}",
                unsafe_allow_html=True,
            )
            if action.get("latest_comment"):
                st.info(truncate(str(action["latest_comment"]), 220))
            render_calendar_tools(
                action,
                language,
                lead_name=str(action["lead_name"]),
                key_prefix=f"my_actions_{action['id']}",
            )
            quick = st.text_area(t("comments.quick_add", language), key=f"comment_{action['id']}", height=80)
            col1, col2, col3 = st.columns(3)
            if col1.button("💬 " + t("comments.save", language), key=f"save_{action['id']}", use_container_width=True):
                with st.spinner(t("spinner.comment", language)):
                    add_comment(
                        conn,
                        organization_id=str(session["organization_id"]),
                        lead_id=str(action["lead_id"]),
                        action_id=str(action["id"]),
                        org_user_id=str(session["org_user_id"]),
                        body=quick,
                    )
                    conn.commit()
                st.success(t("comments.saved", language))
                st.rerun()
            if col2.button("✅ " + t("action.complete", language), key=f"complete_{action['id']}", use_container_width=True):
                st.session_state["guided_focus_action_id"] = action["id"]
                st.session_state["page"] = "next_action"
                st.session_state.pop("guided_action_flow", None)
                st.rerun()
            if col3.button("💬 " + t("lead.open", language), key=f"lead_{action['id']}", use_container_width=True):
                st.session_state["selected_lead_id"] = action["lead_id"]
                st.session_state["page"] = "lead_board"
                st.rerun()
