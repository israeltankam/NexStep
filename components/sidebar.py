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

    pages = [
        ("next_action", "🚀 " + t("nav.next_action", language)),
        ("new_lead", "➕ " + t("nav.new_lead", language)),
        ("my_actions", "✅ " + t("nav.my_actions", language)),
        ("lead_detail", "💬 " + t("nav.lead_detail", language)),
    ]
    if session.get("can_view_team"):
        pages.append(("team_map", "🗺️ " + t("nav.team_map", language)))
    if session.get("role") == "super_admin":
        pages.append(("admin", "⚙️ " + t("nav.admin", language)))

    current = st.session_state.get("page", "next_action")
    keys = [key for key, _ in pages]
    labels = [label for _, label in pages]
    selected_label = st.sidebar.radio(
        t("nav.menu", language),
        labels,
        index=keys.index(current) if current in keys else 0,
        label_visibility="collapsed",
    )
    selected = keys[labels.index(selected_label)]

    st.sidebar.divider()
    language_choice = st.sidebar.selectbox(
        t("settings.language", language),
        ["fr", "en"],
        index=0 if language == "fr" else 1,
        format_func=lambda value: "Français" if value == "fr" else "English",
    )
    if language_choice != language:
        st.session_state["session"]["language"] = language_choice
        st.rerun()

    with st.sidebar.expander(t("help.title", language), expanded=False):
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
    st.sidebar.image(str(SCALEAG_LOGO), width=110)
    st.sidebar.caption("scale.ag")
    return selected
