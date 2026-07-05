"""Simple lead creation page for agents."""

from __future__ import annotations

import datetime as dt
import sqlite3

import streamlit as st

from services.lead_service import list_reference_values
from services.new_lead_service import create_lead_with_first_action
from utils.dates import today
from utils.i18n import t


def _due_date_from_choice(choice: str, custom_date: dt.date | None) -> str | None:
    """Convert the ergonomic delay selector into a database ISO date."""

    delays = {"today": 0, "tomorrow": 1, "3": 3, "7": 7, "14": 14, "30": 30}
    if choice == "custom" and custom_date:
        return custom_date.isoformat()
    if choice in delays:
        return (today() + dt.timedelta(days=delays[choice])).isoformat()
    return None


def _select_optional(label: str, values: list[str]) -> str | None:
    """Render an optional selectbox without exposing an implementation placeholder."""

    options = ["", *values]
    selected = st.selectbox(label, options, format_func=lambda value: "—" if value == "" else value)
    return selected or None


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    organization_id = str(session["organization_id"])
    org_user_id = str(session["org_user_id"])

    st.title("➕ " + t("new_lead.title", language))
    st.caption(t("new_lead.caption", language))

    categories = list_reference_values(conn, organization_id, "client_categories")
    action_types = list_reference_values(conn, organization_id, "action_types")
    default_action_index = action_types.index("Appel") if "Appel" in action_types else 0

    with st.form("new_lead_form", clear_on_submit=False):
        st.subheader(t("new_lead.identity_section", language))
        lead_name = st.text_input(t("new_lead.name", language))
        col1, col2 = st.columns(2)
        with col1:
            contact_name = st.text_input(t("new_lead.contact_name", language))
            phone_raw = st.text_input(t("new_lead.phone", language))
        with col2:
            channel_notes = st.text_input(t("new_lead.channel", language))
            category_name = _select_optional(t("new_lead.category", language), categories)
        city = st.text_input(t("new_lead.city", language))
        context_note = st.text_area(t("new_lead.context", language), height=90)

        st.subheader(t("new_lead.action_section", language))
        col3, col4 = st.columns(2)
        with col3:
            action_type = st.selectbox(t("new_lead.action_type", language), action_types, index=default_action_index)
            action_title = st.text_input(t("new_lead.action_title", language), value=t("new_lead.default_action_title", language))
        with col4:
            delay = st.selectbox(
                t("new_lead.delay", language),
                ["today", "tomorrow", "3", "7", "14", "30", "custom", "none"],
                index=1,
                format_func=lambda value: t(f"delay.{value}", language),
            )
            custom_due = st.date_input(t("new_lead.custom_date", language), value=today()) if delay == "custom" else None
        action_details = st.text_area(t("new_lead.action_details", language), height=90)

        submitted = st.form_submit_button("➕ " + t("new_lead.submit", language), use_container_width=True)
        if submitted:
            with st.spinner(t("spinner.new_lead", language)):
                try:
                    result = create_lead_with_first_action(
                        conn,
                        organization_id=organization_id,
                        actor_org_user_id=org_user_id,
                        lead_name=lead_name,
                        category_name=category_name,
                        contact_name=contact_name,
                        phone_raw=phone_raw,
                        channel_notes=channel_notes,
                        city=city,
                        context_note=context_note,
                        action_type_name=action_type,
                        action_title=action_title,
                        due_date=_due_date_from_choice(delay, custom_due),
                        action_details=action_details,
                    )
                except ValueError as exc:
                    if str(exc) == "lead_name_required":
                        st.error(t("new_lead.error_name_required", language))
                    else:
                        st.error(str(exc))
                    return
            st.session_state["selected_lead_id"] = result["lead_id"]
            st.session_state["new_lead_created"] = result
            st.success(t("new_lead.success", language))

    if st.session_state.get("new_lead_created"):
        col5, col6 = st.columns(2)
        if col5.button("💬 " + t("lead.open", language), use_container_width=True):
            st.session_state["page"] = "lead_detail"
            st.session_state.pop("new_lead_created", None)
            st.rerun()
        if col6.button("✅ " + t("nav.my_actions", language), use_container_width=True):
            st.session_state["page"] = "my_actions"
            st.session_state.pop("new_lead_created", None)
            st.rerun()
