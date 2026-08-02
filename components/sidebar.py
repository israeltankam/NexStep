"""Sidebar navigation with required NexStep and scale.ag branding."""

from __future__ import annotations

import sqlite3

import streamlit as st

from services.access_service import create_quick_access_file, revoke_quick_access
from services.user_profile_service import (
    get_user_contact_details,
    update_own_contact_details,
)
from utils.i18n import t
from utils.paths import MIGRATION_GUIDE_HTML, NEXSTEP_LOGO, SCALEAG_LOGO, USER_GUIDE_HTML
from utils.ui import image_data_uri


def render_sidebar(conn: sqlite3.Connection, session: dict[str, object]) -> str:
    language = str(session.get("language", "fr"))
    st.sidebar.markdown(
        f"<div class='nex-sidebar-logo'><img src='{image_data_uri(NEXSTEP_LOGO)}' alt='NexStep'></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"{session['organization_name']} · {session['display_name']}")

    # Keep every useful destination directly reachable from the navigation.
    pages = [
        ("next_action", "🚀 " + t("nav.next_action", language)),
        ("new_lead", "➕ " + t("nav.new_lead", language)),
        ("lead_board", "📊 " + t("nav.lead_board", language)),
        ("my_actions", "✅ " + t("nav.my_actions", language)),
    ]
    if session.get("role") in {"super_admin", "company_admin"} or session.get("is_global_admin"):
        pages.append(("admin", "⚙️ " + t("nav.admin", language)))

    current = st.session_state.get("page", "next_action")
    keys = [key for key, _ in pages]
    labels = [label for _, label in pages]
    selected_label = st.sidebar.radio(
        t("nav.menu", language),
        labels,
        index=keys.index(current) if current in keys else None,
        label_visibility="collapsed",
    )
    selected = keys[labels.index(selected_label)] if selected_label else current

    st.sidebar.divider()
    with st.sidebar.expander(t("help.title", language), expanded=False):
        language_choice = st.selectbox(
            t("settings.language", language),
            ["fr", "en"],
            index=0 if language == "fr" else 1,
            format_func=lambda value: "Français" if value == "fr" else "English",
        )
        if language_choice != language:
            st.session_state["session"]["language"] = language_choice
            st.rerun()
        st.divider()
        contact_details = get_user_contact_details(conn, str(session["user_id"]))
        with st.form("help_contact_details"):
            st.caption(t("help.contact_title", language))
            st.caption(t("help.contact_hint", language))
            email = st.text_input(
                t("help.contact_email", language),
                value=contact_details["email"],
            )
            phone = st.text_input(
                t("help.contact_phone", language),
                value=contact_details["phone"],
            )
            if st.form_submit_button(
                t("help.contact_save", language),
                use_container_width=True,
            ):
                try:
                    with st.spinner(t("help.contact_saving", language)):
                        update_own_contact_details(
                            conn,
                            user_id=str(session["user_id"]),
                            organization_id=str(session["organization_id"]),
                            email=email,
                            phone=phone,
                        )
                except ValueError as exc:
                    st.error(t(f"help.contact_{exc}", language))
                else:
                    st.success(t("help.contact_saved", language))
        if USER_GUIDE_HTML.exists():
            st.download_button(
                t("help.user_guide", language),
                USER_GUIDE_HTML.read_bytes(),
                file_name="guide_utilisateur_nexstep.html",
                mime="text/html",
                use_container_width=True,
            )
        if MIGRATION_GUIDE_HTML.exists() and session.get("is_global_admin"):
            st.download_button(
                t("help.migration_guide", language),
                MIGRATION_GUIDE_HTML.read_bytes(),
                file_name="guide_migration_sqlite_postgresql_nexstep.html",
                mime="text/html",
                use_container_width=True,
            )
        st.divider()
        st.caption(t("quick_access.sidebar_hint", language))
        if st.button(
            t("quick_access.create", language),
            key="quick_access_create",
            use_container_width=True,
        ):
            with st.spinner(t("quick_access.creating", language)):
                session_id, file_bytes = create_quick_access_file(
                    conn,
                    organization_id=str(session["organization_id"]),
                    user_id=str(session["user_id"]),
                    org_user_id=str(session["org_user_id"]),
                )
            session["quick_access_session_id"] = session_id
            st.session_state["quick_access_download"] = file_bytes
        if file_bytes := st.session_state.get("quick_access_download"):
            st.download_button(
                t("quick_access.download", language),
                file_bytes,
                file_name="acces_nexstep.nexstep",
                mime="application/json",
                use_container_width=True,
            )
        if session.get("quick_access_session_id") and st.button(
            t("quick_access.revoke", language),
            key="quick_access_revoke",
            use_container_width=True,
        ):
            revoke_quick_access(
                conn,
                session_id=str(session["quick_access_session_id"]),
                org_user_id=str(session["org_user_id"]),
            )
            session.pop("quick_access_session_id", None)
            st.session_state.pop("quick_access_download", None)
            st.success(t("quick_access.revoked", language))

    if st.sidebar.button(t("login.logout", language), use_container_width=True):
        st.session_state.clear()
        st.rerun()

    st.sidebar.write("")
    st.sidebar.write("")
    st.sidebar.markdown(
        f"""
        <a class="nex-scale-logo-link" href="https://scale-ag.tech/"
           target="_blank" rel="noopener noreferrer" aria-label="scale.ag">
          <img src="{image_data_uri(SCALEAG_LOGO)}" alt="scale.ag">
        </a>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.caption("scale.ag")
    return selected
