"""Agent landing page: the next action should be visible in seconds."""

from __future__ import annotations

import datetime as dt
import sqlite3

import streamlit as st

from services.action_service import complete_action, get_next_action, resolve_org_user_by_pin, transfer_action
from services.comment_service import add_comment, list_comments_for_lead, recent_comments_for_lead
from utils.constants import ACTION_DONE_OPTIONS, OUTCOMES, TOUCHPOINT_TYPES
from utils.dates import today
from utils.i18n import t
from utils.ui import render_action_card, render_comments
from utils.urgency import urgency_color, urgency_labels


def _next_due_date(choice: str, custom_date: dt.date | None) -> str | None:
    base = today()
    delays = {
        "today": 0,
        "tomorrow": 1,
        "3": 3,
        "7": 7,
        "14": 14,
        "30": 30,
    }
    if choice == "custom" and custom_date:
        return custom_date.isoformat()
    if choice in delays:
        return (base + dt.timedelta(days=delays[choice])).isoformat()
    return None


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    action = get_next_action(conn, str(session["organization_id"]), str(session["org_user_id"]))
    st.title("🚀 " + t("next.title", language))
    if not action:
        st.success(t("next.empty", language))
        return

    action_dict = dict(action)
    action_dict["urgency_color"] = urgency_color(action["due_date"])
    labels = urgency_labels(language)
    render_action_card(action_dict, urgency_label=labels[action_dict["urgency_color"]])

    comments = recent_comments_for_lead(conn, action["lead_id"], limit=3)
    st.subheader("💬 " + t("comments.latest", language))
    render_comments(comments)
    with st.expander(t("comments.full_history", language)):
        render_comments(list_comments_for_lead(conn, action["lead_id"]), max_preview=2000)

    with st.form(f"quick_comment_{action['id']}"):
        body = st.text_area(t("comments.quick_add", language), height=90)
        submitted = st.form_submit_button("💬 " + t("comments.save", language))
        if submitted:
            with st.spinner(t("spinner.comment", language)):
                add_comment(
                    conn,
                    organization_id=action["organization_id"],
                    lead_id=action["lead_id"],
                    action_id=action["id"],
                    org_user_id=str(session["org_user_id"]),
                    body=body,
                    comment_type="general",
                )
                conn.commit()
            st.success(t("comments.saved", language))
            st.rerun()

    col1, col2, col3 = st.columns(3)
    if col1.button("✅ " + t("action.complete", language), use_container_width=True):
        st.session_state["show_complete_form"] = True
    if col2.button("📋 " + t("action.skip", language), use_container_width=True):
        st.session_state["page"] = "my_actions"
        st.rerun()
    if col3.button("💬 " + t("lead.open", language), use_container_width=True):
        st.session_state["selected_lead_id"] = action["lead_id"]
        st.session_state["page"] = "lead_detail"
        st.rerun()

    with st.expander("🔁 " + t("transfer.title", language)):
        target_pin = st.text_input(t("transfer.target_pin", language), type="password")
        note = st.text_area(t("transfer.note", language), height=90)
        if target_pin:
            target = resolve_org_user_by_pin(conn, action["organization_id"], target_pin)
            if target:
                st.info(t("transfer.confirm_to", language, name=target["display_name"]))
        if st.button("🔁 " + t("transfer.submit", language), use_container_width=True):
            with st.spinner(t("spinner.transfer", language)):
                try:
                    result = transfer_action(
                        conn,
                        action_id=action["id"],
                        actor_org_user_id=str(session["org_user_id"]),
                        target_agent_pin=target_pin,
                        transfer_note=note,
                    )
                    st.success(t("transfer.done", language, name=result["target_name"]))
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    if st.session_state.get("show_complete_form"):
        st.subheader("✅ " + t("complete.title", language))
        with st.form(f"complete_{action['id']}"):
            done = st.selectbox(t("complete.done", language), ACTION_DONE_OPTIONS)
            touchpoint_type = st.selectbox(t("complete.touchpoint_type", language), TOUCHPOINT_TYPES)
            outcome = st.selectbox(t("complete.outcome", language), OUTCOMES)
            note = st.text_area(t("complete.note", language), height=110)
            contact_name = st.text_input(t("complete.contact", language), value=action["contact_name"] or "")
            obstacle = st.text_input(t("complete.obstacle", language), value=action["obstacle"] or "")
            decision = st.text_input(t("complete.decision", language))
            create_next = st.checkbox(t("next_action.create", language), value=True)
            next_due_choice = st.selectbox(
                t("next_action.delay", language),
                ["tomorrow", "3", "7", "14", "30", "today", "custom", "none"],
                format_func=lambda value: t(f"delay.{value}", language),
            )
            custom_due = st.date_input(t("next_action.custom_date", language), value=today()) if next_due_choice == "custom" else None
            next_type = st.selectbox(t("next_action.type", language), TOUCHPOINT_TYPES)
            next_title = st.text_input(t("next_action.title", language), value=next_type)
            next_comment = st.text_area(t("next_action.comment", language), height=90)
            other_agent_pin = st.text_input(t("next_action.other_agent_pin", language), type="password")
            submitted = st.form_submit_button("✅ " + t("complete.submit", language))
            if submitted:
                with st.spinner(t("spinner.complete", language)):
                    target_org_user_id = None
                    if other_agent_pin.strip():
                        target = resolve_org_user_by_pin(conn, action["organization_id"], other_agent_pin)
                        if not target:
                            st.error(t("transfer.not_found", language))
                            return
                        target_org_user_id = target["id"]
                    complete_action(
                        conn,
                        action_id=action["id"],
                        actor_org_user_id=str(session["org_user_id"]),
                        completion_status=done,
                        touchpoint_type=touchpoint_type,
                        outcome=outcome,
                        note=note,
                        contact_name=contact_name,
                        obstacle=obstacle,
                        decision=decision,
                        create_next=create_next,
                        next_due_date=_next_due_date(next_due_choice, custom_due),
                        next_action_type=next_type,
                        next_title=next_title,
                        next_comment=next_comment,
                        next_assigned_org_user_id=target_org_user_id,
                    )
                st.session_state["show_complete_form"] = False
                st.success(t("complete.done_message", language))
                st.rerun()
