"""NexStep Streamlit entry point."""

from __future__ import annotations

import sqlite3

import streamlit as st

from components.sidebar import render_sidebar
from database.connection import get_connection
from pages import admin, lead_detail, my_actions, next_action, team_map
from services.auth_service import (
    build_session_payload,
    identify_by_pins,
    password_mode,
    set_user_password,
    verify_user_password,
)
from services.seed_service import ensure_seed_data
from utils.i18n import t
from utils.paths import NEXSTEP_LOGO, USER_GUIDE_HTML
from utils.ui import image_data_uri, inject_css


def _connection() -> sqlite3.Connection:
    conn = get_connection()
    ensure_seed_data(conn)
    return conn


def _load_pending_rows(conn: sqlite3.Connection) -> tuple[sqlite3.Row, sqlite3.Row, sqlite3.Row] | None:
    pending = st.session_state.get("pending_auth")
    if not pending:
        return None
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (pending["organization_id"],)).fetchone()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (pending["user_id"],)).fetchone()
    org_user = conn.execute("SELECT * FROM organization_users WHERE id = ?", (pending["org_user_id"],)).fetchone()
    if org and user and org_user:
        return org, user, org_user
    st.session_state.pop("pending_auth", None)
    return None


def _finish_login(organization: sqlite3.Row, user: sqlite3.Row, org_user: sqlite3.Row) -> None:
    st.session_state["session"] = build_session_payload(organization, user, org_user)
    st.session_state.pop("pending_auth", None)
    st.session_state["page"] = "admin" if org_user["role"] == "super_admin" else "next_action"
    st.rerun()


def render_login(conn: sqlite3.Connection) -> None:
    language = st.session_state.get("login_language", "fr")
    st.markdown(
        f"<div class='nex-login-logo'><img src='{image_data_uri(NEXSTEP_LOGO)}' alt='NexStep'></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div class='nex-logo-caption'>by scale.ag</div>", unsafe_allow_html=True)
    st.write("")
    st.session_state["login_language"] = st.selectbox(
        t("settings.language", language),
        ["fr", "en"],
        index=0 if language == "fr" else 1,
        format_func=lambda value: "Français" if value == "fr" else "English",
    )
    language = st.session_state["login_language"]
    if USER_GUIDE_HTML.exists():
        st.download_button(
            t("help.user_guide", language),
            USER_GUIDE_HTML.read_bytes(),
            file_name="guide_utilisateur_nexstep.html",
            mime="text/html",
            use_container_width=True,
        )

    pending_rows = _load_pending_rows(conn)
    if not pending_rows:
        with st.form("pin_login"):
            company_pin = st.text_input(t("login.company_pin", language), type="password")
            agent_pin = st.text_input(t("login.agent_pin", language), type="password")
            submitted = st.form_submit_button(t("login.continue", language), use_container_width=True)
            if submitted:
                with st.spinner(t("spinner.login", language)):
                    result = identify_by_pins(conn, company_pin, agent_pin)
                if not result.ok:
                    st.error(t(result.message_key, language))
                else:
                    st.session_state["pending_auth"] = {
                        "organization_id": result.organization["id"],
                        "user_id": result.user["id"],
                        "org_user_id": result.org_user["id"],
                    }
                    st.rerun()
        return

    organization, user, org_user = pending_rows
    mode = password_mode(user)
    st.info(t(f"login.{mode}_hello", language, name=user["display_name"]))
    with st.form("password_login"):
        current_password = None
        if mode in {"login", "change"}:
            current_password = st.text_input(t("login.password", language), type="password")
        new_password = None
        confirm_password = None
        if mode in {"setup", "change"}:
            new_password = st.text_input(t("login.new_password", language), type="password")
            confirm_password = st.text_input(t("login.confirm_password", language), type="password")
        submitted = st.form_submit_button(t("login.submit_password", language), use_container_width=True)
        if submitted:
            with st.spinner(t("spinner.login", language)):
                if mode == "login":
                    if verify_user_password(user, current_password or ""):
                        _finish_login(organization, user, org_user)
                    st.error(t("login.invalid_password", language))
                    return
                if mode == "change" and not verify_user_password(user, current_password or ""):
                    st.error(t("login.invalid_password", language))
                    return
                if not new_password or len(new_password) < 4:
                    st.error(t("login.password_too_short", language))
                    return
                if new_password != confirm_password:
                    st.error(t("login.password_mismatch", language))
                    return
                set_user_password(conn, user["id"], new_password)
                refreshed_user = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
                _finish_login(organization, refreshed_user, org_user)


def main() -> None:
    st.set_page_config(page_title="NexStep by scale.ag", page_icon="🚀", layout="wide")
    inject_css()
    conn = _connection()
    if "session" not in st.session_state:
        render_login(conn)
        return

    selected = render_sidebar(st.session_state["session"])
    st.session_state["page"] = selected
    routes = {
        "next_action": next_action.render,
        "my_actions": my_actions.render,
        "lead_detail": lead_detail.render,
        "team_map": team_map.render,
        "admin": admin.render,
    }
    routes.get(selected, next_action.render)(conn, st.session_state["session"])


if __name__ == "__main__":
    main()
