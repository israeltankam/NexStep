"""Guided prospect creation with an immediate first action."""

from __future__ import annotations

import sqlite3

import streamlit as st

from components.guided import render_choice_grid, render_progress
from services.lead_service import list_reference_values
from services.new_lead_service import create_lead_with_first_action
from utils.dates import today
from utils.guided_flow import action_value, due_date_from_choice
from utils.i18n import t


FLOW_KEY = "guided_new_prospect_flow"


def _new_flow() -> dict[str, object]:
    return {
        "step": "identity",
        "name": "",
        "contact_name": "",
        "phone": "",
        "action": None,
        "due": None,
    }


def _flow() -> dict[str, object]:
    """Return the in-session draft; no partial prospect is written to the DB."""

    if FLOW_KEY not in st.session_state:
        st.session_state[FLOW_KEY] = _new_flow()
    return st.session_state[FLOW_KEY]


def _go_back(flow: dict[str, object]) -> None:
    previous = {
        "identity": None,
        "action": "identity",
        "due": "action",
        "confirm": "due",
    }
    target = previous.get(str(flow["step"]))
    if target is None:
        st.session_state.pop(FLOW_KEY, None)
        st.session_state["page"] = "next_action"
    else:
        flow["step"] = target
    st.rerun()


def _back_button(flow: dict[str, object], language: str, suffix: str) -> None:
    if st.button("←", key=f"new_prospect_back_{suffix}", help=t("guided.back", language)):
        _go_back(flow)


def _identity_step(flow: dict[str, object], language: str) -> None:
    render_progress(1, 4, language)
    st.subheader(t("guided.prospect_identity_question", language))
    st.caption(t("guided.prospect_identity_hint", language))
    with st.form("guided_prospect_identity"):
        name = st.text_input(t("new_lead.name", language), value=str(flow.get("name") or ""))
        col_contact, col_phone = st.columns(2)
        contact_name = col_contact.text_input(
            t("new_lead.contact_name", language),
            value=str(flow.get("contact_name") or ""),
        )
        phone = col_phone.text_input(
            t("new_lead.phone", language),
            value=str(flow.get("phone") or ""),
        )
        submitted = st.form_submit_button(
            t("guided.continue", language),
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    if not name.strip():
        st.error(t("new_lead.error_name_required", language))
        return
    flow.update(
        {
            "name": name.strip(),
            "contact_name": contact_name.strip(),
            "phone": phone.strip(),
            "step": "action",
        }
    )
    st.rerun()


def _action_step(flow: dict[str, object], language: str) -> None:
    render_progress(2, 4, language)
    st.subheader(t("guided.prospect_action_question", language))
    selected = render_choice_grid(
        [
            ("call", "☎", t("guided.action.call", language)),
            ("message", "💬", t("guided.action.message", language)),
            ("visit", "📍", t("guided.action.visit", language)),
            ("meeting", "📅", t("guided.action.meeting", language)),
        ],
        key_prefix="new_prospect_action",
    )
    if selected:
        flow["action"] = selected
        flow["step"] = "due"
        st.rerun()
    _back_button(flow, language, "action")


def _due_step(flow: dict[str, object], language: str) -> None:
    render_progress(3, 4, language)
    st.subheader(t("guided.prospect_when_question", language))
    selected = render_choice_grid(
        [
            ("today", "●", t("delay.today", language)),
            ("tomorrow", "→", t("delay.tomorrow", language)),
            ("3", "+3", t("delay.3", language)),
            ("7", "+7", t("delay.7", language)),
            ("custom", "📅", t("delay.custom", language)),
            ("none", "∞", t("delay.none", language)),
        ],
        key_prefix="new_prospect_due",
    )
    if selected and selected != "custom":
        flow["due"] = selected
        flow["step"] = "confirm"
        st.rerun()
    if selected == "custom":
        flow["due"] = "custom"

    if flow.get("due") == "custom":
        custom_due = st.date_input(t("new_lead.custom_date", language), value=today())
        if st.button(
            t("guided.continue", language),
            key="new_prospect_custom_due_continue",
            type="primary",
            use_container_width=True,
        ):
            flow["custom_due"] = custom_due
            flow["step"] = "confirm"
            st.rerun()
    _back_button(flow, language, "due")


def _confirmation_step(
    conn: sqlite3.Connection,
    session: dict[str, object],
    flow: dict[str, object],
    language: str,
) -> None:
    render_progress(4, 4, language)
    st.subheader(t("guided.prospect_confirm_question", language))

    action_key = str(flow["action"])
    due_key = str(flow["due"])
    due_label = str(flow.get("custom_due")) if due_key == "custom" else t(f"delay.{due_key}", language)
    st.markdown(
        t(
            "guided.prospect_summary",
            language,
            name=flow["name"],
            action=t(f"guided.action.{action_key}", language),
            due=due_label,
        )
    )

    categories = list_reference_values(conn, str(session["organization_id"]), "client_categories")
    with st.expander(t("guided.optional_details", language), expanded=False):
        channel_notes = st.text_input(t("new_lead.channel", language))
        city = st.text_input(t("new_lead.city", language))
        category_name = st.selectbox(
            t("new_lead.category", language),
            ["", *categories],
            format_func=lambda value: "—" if value == "" else value,
        )
        context_note = st.text_area(t("new_lead.context", language), height=80)
        action_details = st.text_area(t("new_lead.action_details", language), height=80)

    col_back, col_create = st.columns([1, 4])
    if col_back.button("←", key="new_prospect_confirm_back", help=t("guided.back", language)):
        _go_back(flow)
    if not col_create.button(
        "✓  " + t("guided.prospect_create", language),
        key="new_prospect_create",
        type="primary",
        use_container_width=True,
    ):
        return

    with st.spinner(t("spinner.new_lead", language)):
        action_type = action_value(action_key)
        try:
            create_lead_with_first_action(
                conn,
                organization_id=str(session["organization_id"]),
                actor_org_user_id=str(session["org_user_id"]),
                lead_name=str(flow["name"]),
                category_name=category_name or None,
                contact_name=str(flow.get("contact_name") or ""),
                phone_raw=str(flow.get("phone") or ""),
                channel_notes=channel_notes,
                city=city,
                context_note=context_note,
                action_type_name=action_type,
                action_title=t(f"guided.action.{action_key}", language),
                due_date=due_date_from_choice(
                    due_key,
                    flow.get("custom_due") if due_key == "custom" else None,
                ),
                action_details=action_details,
            )
        except ValueError as exc:
            if str(exc) == "lead_name_required":
                st.error(t("new_lead.error_name_required", language))
            else:
                st.error(str(exc))
            return

    st.session_state.pop(FLOW_KEY, None)
    st.session_state["guided_flash"] = t("new_lead.success", language)
    st.session_state["page"] = "next_action"
    st.rerun()


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    flow = _flow()

    st.title("➕ " + t("new_lead.title", language))
    st.caption(t("new_lead.caption", language))

    step = flow["step"]
    if step == "identity":
        _identity_step(flow, language)
    elif step == "action":
        _action_step(flow, language)
    elif step == "due":
        _due_step(flow, language)
    else:
        _confirmation_step(conn, session, flow, language)
