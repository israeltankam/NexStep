"""Guided agent landing page: one useful decision at a time."""

from __future__ import annotations

import sqlite3

import streamlit as st

from components.guided import (
    render_action_focus,
    render_choice_grid,
    render_latest_note,
    render_progress,
)
from services.action_service import complete_action, list_actions, resolve_org_user_by_pin, transfer_action
from services.comment_service import add_comment, list_comments_for_lead
from utils.dates import today
from utils.guided_flow import action_value, due_date_from_choice, outcome_value, touchpoint_value
from utils.i18n import t
from utils.ui import render_comments
from utils.urgency import urgency_labels


FLOW_KEY = "guided_action_flow"
SKIPPED_KEY = "guided_skipped_actions"


def _start_flow(action_id: str) -> None:
    """Start a fresh completion flow tied to the action currently displayed."""

    st.session_state[FLOW_KEY] = {
        "action_id": action_id,
        "step": "outcome",
        "outcome": None,
        "next_action": None,
        "due": None,
    }


def _flow_for(action_id: str) -> dict[str, object] | None:
    """Discard stale wizard state when the visible action has changed."""

    flow = st.session_state.get(FLOW_KEY)
    if flow and flow.get("action_id") != action_id:
        st.session_state.pop(FLOW_KEY, None)
        return None
    return flow


def _back(flow: dict[str, object]) -> None:
    previous = {
        "outcome": None,
        "next_action": "outcome",
        "due": "next_action",
        "confirm": "due" if flow.get("next_action") != "none" else "next_action",
    }
    target = previous.get(str(flow.get("step")))
    if target is None:
        st.session_state.pop(FLOW_KEY, None)
    else:
        flow["step"] = target
    st.rerun()


def _render_back(flow: dict[str, object], language: str) -> None:
    if st.button("←", key=f"guided_back_{flow['step']}", help=t("guided.back", language)):
        _back(flow)


def _render_outcome_step(flow: dict[str, object], language: str) -> None:
    render_progress(1, 4, language)
    st.subheader(t("guided.outcome_question", language))
    selected = render_choice_grid(
        [
            ("interested", "👍", t("guided.outcome.interested", language)),
            ("callback", "🔁", t("guided.outcome.callback", language)),
            ("unavailable", "⏳", t("guided.outcome.unavailable", language)),
            ("refusal", "✕", t("guided.outcome.refusal", language)),
        ],
        key_prefix="guided_outcome",
    )
    if selected:
        flow["outcome"] = selected
        flow["step"] = "next_action"
        st.rerun()
    _render_back(flow, language)


def _render_next_action_step(flow: dict[str, object], language: str) -> None:
    render_progress(2, 4, language)
    st.subheader(t("guided.next_question", language))
    selected = render_choice_grid(
        [
            ("call", "☎", t("guided.action.call", language)),
            ("message", "💬", t("guided.action.message", language)),
            ("meeting", "📅", t("guided.action.meeting", language)),
            ("none", "✓", t("guided.action.none", language)),
        ],
        key_prefix="guided_next",
    )
    if selected:
        flow["next_action"] = selected
        flow["due"] = None
        flow["step"] = "confirm" if selected == "none" else "due"
        st.rerun()
    _render_back(flow, language)


def _render_due_step(flow: dict[str, object], language: str) -> None:
    render_progress(3, 4, language)
    st.subheader(t("guided.when_question", language))
    selected = render_choice_grid(
        [
            ("today", "●", t("delay.today", language)),
            ("tomorrow", "→", t("delay.tomorrow", language)),
            ("3", "+3", t("delay.3", language)),
            ("7", "+7", t("delay.7", language)),
            ("custom", "📅", t("delay.custom", language)),
            ("none", "∞", t("delay.none", language)),
        ],
        key_prefix="guided_due",
    )
    if selected and selected != "custom":
        flow["due"] = selected
        flow["step"] = "confirm"
        st.rerun()
    if selected == "custom":
        flow["due"] = "custom"

    if flow.get("due") == "custom":
        custom_due = st.date_input(t("next_action.custom_date", language), value=today())
        if st.button(
            t("guided.continue", language),
            key="guided_custom_due_continue",
            type="primary",
            use_container_width=True,
        ):
            flow["custom_due"] = custom_due
            flow["step"] = "confirm"
            st.rerun()
    _render_back(flow, language)


def _render_confirmation(
    conn: sqlite3.Connection,
    session: dict[str, object],
    action: dict[str, object],
    flow: dict[str, object],
    language: str,
) -> None:
    render_progress(4, 4, language)
    st.subheader(t("guided.confirm_question", language))

    outcome_key = str(flow["outcome"])
    next_key = str(flow["next_action"])
    due_key = str(flow.get("due") or "none")
    st.markdown(
        t(
            "guided.summary_result",
            language,
            result=t(f"guided.outcome.{outcome_key}", language),
        )
    )
    if next_key == "none":
        st.markdown(t("guided.summary_no_next", language))
    else:
        due_label = (
            str(flow.get("custom_due"))
            if due_key == "custom"
            else t(f"delay.{due_key}", language)
        )
        st.markdown(
            t(
                "guided.summary_next",
                language,
                action=t(f"guided.action.{next_key}", language),
                due=due_label,
            )
        )

    # These fields preserve the full historical workflow without forcing every
    # agent to process CRM vocabulary during routine work.
    with st.expander(t("guided.optional_details", language), expanded=False):
        note = st.text_area(t("complete.note", language), key="guided_completion_note", height=90)
        contact_name = st.text_input(
            t("complete.contact", language),
            value=str(action.get("contact_name") or ""),
            key="guided_completion_contact",
        )
        obstacle = st.text_input(t("complete.obstacle", language), key="guided_completion_obstacle")
        decision = st.text_input(t("complete.decision", language), key="guided_completion_decision")
        next_comment = st.text_area(
            t("next_action.comment", language),
            key="guided_next_comment",
            height=80,
        )
        other_agent_pin = st.text_input(
            t("next_action.other_agent_pin", language),
            type="password",
            key="guided_other_agent_pin",
        )

    col_back, col_save = st.columns([1, 4])
    if col_back.button("←", key="guided_confirm_back", help=t("guided.back", language)):
        _back(flow)
    if not col_save.button(
        "✓  " + t("guided.save_and_continue", language),
        key="guided_confirm_save",
        type="primary",
        use_container_width=True,
    ):
        return

    with st.spinner(t("spinner.complete", language)):
        target_org_user_id = None
        if other_agent_pin.strip():
            target = resolve_org_user_by_pin(conn, str(action["organization_id"]), other_agent_pin)
            if not target:
                st.error(t("transfer.not_found", language))
                return
            target_org_user_id = str(target["id"])

        next_type = action_value(next_key)
        create_next = next_type is not None
        next_due_date = (
            due_date_from_choice(
                due_key,
                flow.get("custom_due") if due_key == "custom" else None,
            )
            if create_next
            else None
        )
        complete_action(
            conn,
            action_id=str(action["id"]),
            actor_org_user_id=str(session["org_user_id"]),
            completion_status="Oui",
            touchpoint_type=touchpoint_value(str(action.get("action_type_name") or "")),
            outcome=outcome_value(outcome_key),
            note=note,
            contact_name=contact_name,
            obstacle=obstacle,
            decision=decision,
            create_next=create_next,
            next_due_date=next_due_date,
            next_action_type=next_type,
            next_title=t(f"guided.action.{next_key}", language) if create_next else None,
            next_comment=next_comment,
            next_assigned_org_user_id=target_org_user_id,
        )

    st.session_state.pop(FLOW_KEY, None)
    st.session_state.pop(SKIPPED_KEY, None)
    st.session_state.pop("guided_focus_action_id", None)
    st.session_state["guided_flash"] = t("complete.done_message", language)
    st.rerun()


def _render_more_options(
    conn: sqlite3.Connection,
    session: dict[str, object],
    action: dict[str, object],
    language: str,
) -> None:
    with st.expander(t("guided.more_options", language), expanded=False):
        with st.form(f"quick_comment_{action['id']}"):
            body = st.text_area(t("comments.quick_add", language), height=80)
            if st.form_submit_button("💬 " + t("comments.save", language), use_container_width=True):
                with st.spinner(t("spinner.comment", language)):
                    add_comment(
                        conn,
                        organization_id=str(action["organization_id"]),
                        lead_id=str(action["lead_id"]),
                        action_id=str(action["id"]),
                        org_user_id=str(session["org_user_id"]),
                        body=body,
                        comment_type="general",
                    )
                    conn.commit()
                st.session_state["guided_flash"] = t("comments.saved", language)
                st.rerun()

        if st.button("💬 " + t("lead.open", language), key=f"open_lead_{action['id']}"):
            st.session_state["selected_lead_id"] = action["lead_id"]
            st.session_state["page"] = "lead_detail"
            st.rerun()

        st.markdown(f"**{t('transfer.title', language)}**")
        with st.form(f"guided_transfer_{action['id']}"):
            target_pin = st.text_input(t("transfer.target_pin", language), type="password")
            transfer_note = st.text_area(t("transfer.note", language), height=70)
            if st.form_submit_button("↗ " + t("transfer.submit", language), use_container_width=True):
                with st.spinner(t("spinner.transfer", language)):
                    try:
                        result = transfer_action(
                            conn,
                            action_id=str(action["id"]),
                            actor_org_user_id=str(session["org_user_id"]),
                            target_agent_pin=target_pin,
                            transfer_note=transfer_note,
                        )
                    except ValueError:
                        st.error(t("transfer.not_found", language))
                        return
                st.session_state["guided_flash"] = t(
                    "transfer.done", language, name=result["target_name"]
                )
                st.rerun()

    with st.expander(t("comments.full_history", language), expanded=False):
        render_comments(
            list_comments_for_lead(conn, str(action["lead_id"])),
            max_preview=2000,
            empty_label=t("comments.none", language),
        )


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    organization_id = str(session["organization_id"])
    org_user_id = str(session["org_user_id"])

    if flash := st.session_state.pop("guided_flash", None):
        st.success(str(flash))

    st.title("🚀 " + t("next.title", language))
    st.caption(t("guided.next_caption", language))

    actions = list_actions(conn, organization_id, org_user_id=org_user_id)
    skipped = set(st.session_state.get(SKIPPED_KEY, []))
    focus_action_id = st.session_state.get("guided_focus_action_id")
    action = next(
        (
            candidate
            for candidate in actions
            if candidate["id"] == focus_action_id and candidate["id"] not in skipped
        ),
        None,
    )
    if action is None:
        st.session_state.pop("guided_focus_action_id", None)
        action = next((candidate for candidate in actions if candidate["id"] not in skipped), None)

    if not action:
        if actions:
            st.info(t("guided.all_skipped", language))
            if st.button(t("guided.review_again", language), type="primary"):
                st.session_state.pop(SKIPPED_KEY, None)
                st.rerun()
        else:
            st.success(t("next.empty", language))
        return

    labels = urgency_labels(language)
    render_action_focus(action, labels[str(action["urgency_color"])], language)
    render_latest_note(str(action.get("latest_comment") or ""), language)

    flow = _flow_for(str(action["id"]))
    if flow:
        step = flow.get("step")
        if step == "outcome":
            _render_outcome_step(flow, language)
        elif step == "next_action":
            _render_next_action_step(flow, language)
        elif step == "due":
            _render_due_step(flow, language)
        else:
            _render_confirmation(conn, session, action, flow, language)
        return

    col_done, col_later = st.columns([3, 2])
    if col_done.button(
        "✓  " + t("guided.done_button", language),
        type="primary",
        use_container_width=True,
    ):
        _start_flow(str(action["id"]))
        st.rerun()
    if col_later.button(
        "→  " + t("guided.later_button", language),
        use_container_width=True,
    ):
        st.session_state.pop("guided_focus_action_id", None)
        st.session_state.setdefault(SKIPPED_KEY, []).append(action["id"])
        st.rerun()

    _render_more_options(conn, session, action, language)
