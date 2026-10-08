"""Read-only team activity, one small page at a time."""

from __future__ import annotations

import sqlite3

import streamlit as st

from services.team_actions_service import PAGE_SIZE, list_team_actions
from utils.i18n import t


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    st.title("👥 " + t("team_actions.title", language))
    offset = int(st.session_state.get("team_actions_offset", 0))
    try:
        with st.spinner(t("team_actions.loading", language)):
            page = list_team_actions(conn,
                organization_id=str(session["organization_id"]),
                actor_org_user_id=str(session["org_user_id"]), offset=offset)
    except PermissionError:
        st.error(t("team_actions.forbidden", language))
        return
    if not page.actions:
        if offset > 0:
            # Completed actions can disappear after a filter or data correction.
            st.session_state["team_actions_offset"] = max(0, offset - PAGE_SIZE)
            st.rerun()
        st.info(t("team_actions.empty", language))
        return

    st.caption(t("team_actions.range", language,
                 first=offset + 1, last=offset + len(page.actions)))
    for action in page.actions:
        with st.container(border=True):
            st.markdown(f"**{action['title']}**")
            st.caption(t("team_actions.item", language,
                         lead=action["lead_name"],
                         agent=action["completed_by_name"] or t("team_actions.unknown_agent", language),
                         date=action["completed_at"]))
            if action["completion_note"]:
                st.write(action["completion_note"])

    previous, following = st.columns(2)
    if previous.button(t("team_actions.previous", language), disabled=offset == 0,
                       use_container_width=True):
        st.session_state["team_actions_offset"] = max(0, offset - PAGE_SIZE)
        st.rerun()
    if following.button(t("team_actions.next", language), disabled=not page.has_more,
                        use_container_width=True):
        st.session_state["team_actions_offset"] = offset + PAGE_SIZE
        st.rerun()
