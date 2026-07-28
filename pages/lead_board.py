"""Interactive Lead Board replacing technical prospect and team views."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from components.calendar_tools import render_calendar_tools
from services.comment_service import add_comment
from services.lead_board_service import (
    build_lead_board,
    filter_lead_board,
    get_board_lead,
    lead_board_excel,
    list_team_members,
    team_board_summary,
)
from utils.dates import format_date
from utils.i18n import t
from utils.ui import render_comments, urgency_badge
from utils.urgency import urgency_label, urgency_labels


def _filter_rows(
    rows: list[dict[str, object]],
    members: list[dict[str, object]],
    language: str,
    can_view_team: bool,
) -> list[dict[str, object]]:
    """Render compact filters and return the matching board rows."""

    search = st.text_input(t("board.search", language), placeholder=t("board.search_hint", language))
    urgency_map = {label: color for color, label in urgency_labels(language).items()}
    stages = sorted({str(row["stage_name"]) for row in rows if row.get("stage_name")})
    statuses = sorted({str(row["status_name"]) for row in rows if row.get("status_name")})

    first, second, third = st.columns(3)
    selected_urgencies = first.multiselect(
        t("board.filter_urgency", language),
        list(urgency_map),
        default=list(urgency_map),
    )
    selected_stages = second.multiselect(
        t("board.filter_stage", language),
        stages,
        default=stages,
    )
    selected_statuses = third.multiselect(
        t("board.filter_status", language),
        statuses,
        default=statuses,
    )

    selected_owner_ids = None
    if can_view_team:
        owner_options = {str(member["display_name"]): str(member["org_user_id"]) for member in members}
        selected_agents = st.multiselect(
            t("board.filter_agents", language),
            list(owner_options),
            default=list(owner_options),
        )
        selected_owner_ids = {owner_options[name] for name in selected_agents}

    return filter_lead_board(
        rows,
        search=search,
        urgency_colors={urgency_map[label] for label in selected_urgencies},
        owner_ids=selected_owner_ids,
        stages=set(selected_stages),
        statuses=set(selected_statuses),
    )


def _display_frame(rows: list[dict[str, object]], language: str) -> pd.DataFrame:
    """Translate internal fields into concise labels an agent can scan."""

    return pd.DataFrame(
        [
            {
                "__lead_id": row["id"],
                t("board.col.prospect", language): row.get("name") or "",
                t("board.col.contacts", language): row.get("contacts_text") or "",
                t("board.col.next_action", language): row.get("next_action_title") or "",
                t("board.col.due", language): format_date(row.get("next_due_date"), ""),
                t("board.col.urgency", language): urgency_label(str(row["urgency_color"]), language),
                t("board.col.agent", language): row.get("owner_name") or t("lead.unassigned", language),
                t("board.col.comment", language): row.get("latest_comment") or "",
                t("board.col.stage", language): row.get("stage_name") or "",
                t("board.col.city", language): row.get("city") or "",
            }
            for row in rows
        ]
    )


def _render_team_summary(
    conn: sqlite3.Connection,
    organization_id: str,
    rows: list[dict[str, object]],
    language: str,
) -> None:
    with st.expander(t("board.team_summary", language), expanded=False):
        summary = team_board_summary(conn, organization_id, rows)
        frame = pd.DataFrame(
            [
                {
                    t("board.team.agent", language): row["display_name"],
                    t("board.team.role", language): row["role"],
                    t("board.team.leads", language): row["lead_count"],
                    t("board.team.pending", language): row["pending_action_count"],
                    t("board.team.overdue", language): row["overdue_count"],
                }
                for row in summary
            ]
        )
        st.dataframe(frame, hide_index=True, use_container_width=True)


def _render_selected_lead(
    conn: sqlite3.Connection,
    session: dict[str, object],
    lead: dict[str, object],
    language: str,
) -> None:
    st.divider()
    st.subheader(str(lead["name"]))
    st.caption(
        " | ".join(
            value
            for value in (
                str(lead.get("stage_name") or ""),
                str(lead.get("status_name") or ""),
                str(lead.get("category_name") or ""),
                str(lead.get("owner_name") or t("lead.unassigned", language)),
            )
            if value
        )
    )
    if lead.get("context_full"):
        st.info(str(lead["context_full"]))

    contacts_tab, actions_tab, comments_tab = st.tabs(
        [
            t("board.contacts_tab", language),
            t("board.actions_tab", language),
            t("board.comments_tab", language),
        ]
    )

    with contacts_tab:
        contacts = lead["contacts"]
        if not contacts:
            st.caption(t("board.no_contacts", language))
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            t("board.contact.name", language): row.get("full_name") or "",
                            t("board.contact.role", language): row.get("role_title") or "",
                            t("board.contact.phone", language): row.get("phone_raw") or "",
                            t("board.contact.email", language): row.get("email") or "",
                            "WhatsApp": row.get("whatsapp") or "",
                            t("board.contact.note", language): row.get("channel_notes") or "",
                        }
                        for row in contacts
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )

    with actions_tab:
        actions = lead["actions"]
        if not actions:
            st.caption(t("board.no_actions", language))
        else:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            t("board.action.title", language): row.get("title") or "",
                            t("board.action.due", language): format_date(row.get("due_date"), ""),
                            t("board.action.status", language): t(
                                f"board.action.status.{row.get('status')}", language
                            ),
                            t("board.action.note", language): row.get("details") or "",
                        }
                        for row in actions
                    ]
                ),
                hide_index=True,
                use_container_width=True,
            )
            next_action = lead.get("next_action")
            if next_action:
                st.markdown(
                    urgency_badge(
                        str(lead["urgency_color"]),
                        urgency_label(str(lead["urgency_color"]), language),
                    ),
                    unsafe_allow_html=True,
                )
                render_calendar_tools(
                    next_action,
                    language,
                    lead_name=str(lead["name"]),
                    location=str(lead.get("address") or lead.get("city") or ""),
                    key_prefix=f"board_{lead['id']}",
                )

    with comments_tab:
        with st.form(f"board_comment_{lead['id']}"):
            body = st.text_area(t("comments.general_add", language), height=90)
            submitted = st.form_submit_button(
                t("comments.save", language),
                use_container_width=True,
            )
        if submitted:
            with st.spinner(t("spinner.comment", language)):
                add_comment(
                    conn,
                    organization_id=str(session["organization_id"]),
                    lead_id=str(lead["id"]),
                    org_user_id=str(session["org_user_id"]),
                    body=body,
                    comment_type="general",
                )
                conn.commit()
            st.success(t("comments.saved", language))
            st.rerun()
        render_comments(
            lead["comments"],
            max_preview=2000,
            empty_label=t("comments.none", language),
        )


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    organization_id = str(session["organization_id"])
    can_view_team = bool(session.get("can_view_team"))
    members = list_team_members(conn, organization_id)
    allowed_owners = None if can_view_team else [str(session["org_user_id"])]

    st.title("Lead Board")
    st.caption(t("board.caption", language))
    rows = build_lead_board(conn, organization_id, allowed_owner_ids=allowed_owners)
    filtered = _filter_rows(rows, members, language, can_view_team)

    if can_view_team:
        _render_team_summary(conn, organization_id, rows, language)

    count_col, export_col = st.columns([3, 1])
    count_col.caption(t("board.count", language, count=len(filtered)))
    export_col.download_button(
        t("board.export_excel", language),
        lead_board_excel(filtered, language),
        file_name="nexstep_lead_board.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
    if not filtered:
        st.info(t("board.empty", language))
        return

    frame = _display_frame(filtered, language)
    event = st.dataframe(
        frame,
        hide_index=True,
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        column_config={"__lead_id": None},
        key="lead_board_table",
    )
    selected_rows = list(event.selection.rows)
    if selected_rows:
        selected_id = str(frame.iloc[selected_rows[0]]["__lead_id"])
        st.session_state["selected_lead_id"] = selected_id

    selected = get_board_lead(rows, st.session_state.get("selected_lead_id"))
    if selected:
        _render_selected_lead(conn, session, selected, language)
