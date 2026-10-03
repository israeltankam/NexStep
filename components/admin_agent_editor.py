"""Compact agent editor for the scale.ag administration page."""

from __future__ import annotations

import sqlite3

import streamlit as st

from services.agent_management_service import AGENT_ROLES, list_editable_agents, update_agent
from utils.i18n import t


def render_agent_editor(conn: sqlite3.Connection, *, actor_user_id: str, language: str) -> None:
    """Choose a company link first so the edited authority is unambiguous."""
    agents = list_editable_agents(conn, actor_user_id=actor_user_id)
    if not agents:
        return
    by_id = {str(agent["org_user_id"]): agent for agent in agents}
    st.subheader(t("admin.edit_agent", language))
    selected_id = st.selectbox(
        t("admin.select_company_agent", language), list(by_id),
        format_func=lambda key: f"{by_id[key]['organization_name']} · {by_id[key]['display_name']}",
        key="edit_agent_selection",
    )
    agent = by_id[selected_id]
    st.caption(t("admin.agent_scope_hint", language))
    with st.form(f"edit_agent_{selected_id}"):
        name = st.text_input(t("admin.display_name", language), value=agent["display_name"] or "",
                             key=f"agent_name_{selected_id}")
        email = st.text_input(t("help.contact_email", language), value=agent["email"] or "",
                              key=f"agent_email_{selected_id}")
        phone = st.text_input(t("help.contact_phone", language), value=agent["phone"] or "",
                              key=f"agent_phone_{selected_id}")
        preferred_language = st.selectbox(t("settings.language", language), ["fr", "en"],
                                          index=0 if agent["preferred_language"] == "fr" else 1,
                                          key=f"agent_language_{selected_id}")
        role = st.selectbox(t("admin.role", language), AGENT_ROLES,
                            index=AGENT_ROLES.index(agent["role"]),
                            format_func=lambda value: t(f"admin.agent_role_{value}", language),
                            key=f"agent_role_{selected_id}")
        if role == "company_admin":
            # Administrators always receive team visibility; avoid a disabled,
            # potentially stale checkbox when switching roles in Streamlit.
            st.caption(t("admin.team_access_included", language))
            can_view_team = True
        else:
            can_view_team = st.checkbox(t("admin.can_view_team", language),
                                        value=bool(agent["can_view_team"]),
                                        key=f"agent_team_{selected_id}")
        link_active = st.checkbox(t("admin.link_active", language), value=bool(agent["link_active"]),
                                  key=f"agent_link_{selected_id}")
        account_active = st.checkbox(t("admin.account_active", language), value=bool(agent["account_active"]),
                                     key=f"agent_account_{selected_id}")
        new_pin = st.text_input(t("admin.optional_new_agent_pin", language), type="password",
                                help=t("admin.optional_pin_hint", language), key=f"agent_pin_{selected_id}")
        submitted = st.form_submit_button(t("admin.save_agent", language), use_container_width=True)
    if not submitted:
        return
    try:
        with st.spinner(t("spinner.admin", language)):
            update_agent(conn, actor_user_id=actor_user_id, org_user_id=selected_id,
                         display_name=name, email=email, phone=phone,
                         preferred_language=preferred_language, role=role,
                         can_view_team=can_view_team, link_active=link_active,
                         account_active=account_active, new_pin=new_pin)
    except PermissionError:
        st.error(t("admin.forbidden", language))
    except ValueError as exc:
        st.error(t(f"admin.agent_error_{exc}", language))
    else:
        st.success(t("admin.agent_saved", language))
        st.rerun()
