"""NexStep Streamlit entry point."""

from __future__ import annotations

import sqlite3

import streamlit as st

from components.sidebar import render_sidebar
from database.connection import DatabaseConfigurationError, DatabaseConnectionError, get_connection
from pages import admin, lead_board, my_actions, new_lead, next_action
from services.auth_service import (
    build_session_payload,
    identify_by_pins,
    password_mode,
    set_user_password,
    verify_user_password,
)
from services.access_service import authenticate_quick_access
from services.password_reset_service import request_password_reset
from services.seed_service import ensure_seed_data
from utils.i18n import t
from utils.paths import NEXSTEP_LOGO, USER_GUIDE_HTML
from utils.ui import image_data_uri, inject_css


@st.cache_resource(show_spinner=False)
def _initialize_database() -> bool:
    """Create/seed the active database once per Streamlit server process."""

    conn = get_connection()
    try:
        ensure_seed_data(conn)
    except Exception as exc:
        raise DatabaseConnectionError("Unable to initialize PostgreSQL.") from exc
    finally:
        conn.close()
    return True


def _connection():
    _initialize_database()
    return get_connection()


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


def _finish_login(
    organization: sqlite3.Row,
    user: sqlite3.Row,
    org_user: sqlite3.Row,
    *,
    quick_access_session_id: str | None = None,
) -> None:
    st.session_state["session"] = build_session_payload(organization, user, org_user)
    if quick_access_session_id:
        st.session_state["session"]["quick_access_session_id"] = quick_access_session_id
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
        with st.expander(t("quick_access.login_title", language), expanded=False):
            access_file = st.file_uploader(
                t("quick_access.upload", language),
                type=["nexstep"],
                key="quick_access_upload",
            )
            if access_file and st.button(
                t("quick_access.open", language),
                key="quick_access_open",
                use_container_width=True,
            ):
                with st.spinner(t("spinner.login", language)):
                    access_result = authenticate_quick_access(conn, access_file.getvalue())
                if not access_result.ok:
                    st.error(t(access_result.message_key, language))
                elif password_mode(access_result.user) != "login":
                    st.session_state["pending_auth"] = {
                        "organization_id": access_result.organization["id"],
                        "user_id": access_result.user["id"],
                        "org_user_id": access_result.org_user["id"],
                    }
                    st.rerun()
                else:
                    _finish_login(
                        access_result.organization,
                        access_result.user,
                        access_result.org_user,
                        quick_access_session_id=access_result.session_id,
                    )

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

    if mode == "login" and st.button(
        t("password_reset.request", language),
        key="request_password_reset",
        use_container_width=True,
    ):
        with st.spinner(t("password_reset.request_spinner", language)):
            request_password_reset(
                conn,
                organization_id=str(organization["id"]),
                user_id=str(user["id"]),
                org_user_id=str(org_user["id"]),
            )
        st.session_state.pop("pending_auth", None)
        st.success(t("password_reset.requested", language))


def main() -> None:
    st.set_page_config(page_title="NexStep by scale.ag", page_icon="🚀", layout="wide")
    inject_css()
    language = st.session_state.get("session", {}).get(
        "language", st.session_state.get("login_language", "fr")
    )
    try:
        with st.spinner(t("spinner.database", language)):
            conn = _connection()
    except DatabaseConfigurationError:
        st.error(t("database.cloud_configuration_error", language))
        st.stop()
    except DatabaseConnectionError:
        st.error(t("database.connection_error", language))
        st.stop()

    try:
        if "session" not in st.session_state:
            render_login(conn)
            return

        selected = render_sidebar(conn, st.session_state["session"])
        st.session_state["page"] = selected
        routes = {
            "next_action": next_action.render,
            "new_lead": new_lead.render,
            "my_actions": my_actions.render,
            "lead_board": lead_board.render,
            # Preserve old in-app destinations while consolidating both views.
            "lead_detail": lead_board.render,
            "team_map": lead_board.render,
            "admin": admin.render,
        }
        routes.get(selected, next_action.render)(conn, st.session_state["session"])
    finally:
        # Streamlit reruns this file after each interaction. Returning the
        # connection promptly prevents exhausting Supabase's connection pool.
        conn.close()


if __name__ == "__main__":
    main()
