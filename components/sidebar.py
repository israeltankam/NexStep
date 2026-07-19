"""Sidebar navigation with required NexStep and scale.ag branding."""

from __future__ import annotations

import streamlit as st

from utils.i18n import t
from utils.paths import MIGRATION_GUIDE_HTML, NEXSTEP_LOGO, SCALEAG_LOGO, USER_GUIDE_HTML
from utils.ui import image_data_uri


def render_sidebar(session: dict[str, object]) -> str:
    language = str(session.get("language", "fr"))
    st.sidebar.markdown(
        f"<div class='nex-sidebar-logo'><img src='{image_data_uri(NEXSTEP_LOGO)}' alt='NexStep'></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption(f"{session['organization_name']} · {session['display_name']}")

    # Routine agent work stays visible. Search, supervision and administration
    # remain available below, but no longer compete with the next useful click.
    pages = [
        ("next_action", "🚀 " + t("nav.next_action", language)),
        ("new_lead", "➕ " + t("nav.new_lead", language)),
        ("my_actions", "✅ " + t("nav.my_actions", language)),
    ]

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

    with st.sidebar.expander(t("nav.more", language), expanded=False):
        if st.button(
            "💬 " + t("nav.lead_detail", language),
            key="nav_lead_detail",
            use_container_width=True,
        ):
            st.session_state["page"] = "lead_detail"
            st.rerun()
        if session.get("can_view_team") and st.button(
            "🗺️ " + t("nav.team_map", language),
            key="nav_team_map",
            use_container_width=True,
        ):
            st.session_state["page"] = "team_map"
            st.rerun()
        if session.get("role") == "super_admin" and st.button(
            "⚙️ " + t("nav.admin", language),
            key="nav_admin",
            use_container_width=True,
        ):
            st.session_state["page"] = "admin"
            st.rerun()

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
        if USER_GUIDE_HTML.exists():
            st.download_button(
                t("help.user_guide", language),
                USER_GUIDE_HTML.read_bytes(),
                file_name="guide_utilisateur_nexstep.html",
                mime="text/html",
                use_container_width=True,
            )
        if MIGRATION_GUIDE_HTML.exists() and session.get("role") == "super_admin":
            st.download_button(
                t("help.migration_guide", language),
                MIGRATION_GUIDE_HTML.read_bytes(),
                file_name="guide_migration_sqlite_postgresql_nexstep.html",
                mime="text/html",
                use_container_width=True,
            )

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
