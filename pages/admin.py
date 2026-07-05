"""scale.ag admin console."""

from __future__ import annotations

import os
import sqlite3

import streamlit as st

from services import admin_service
from services.import_service import import_legacy_rows, read_uploaded_table
from services.migration_service import migrate_sqlite_to_postgres
from services.seed_service import seed_validation_counts
from utils.constants import ROLES
from utils.i18n import t
from utils.paths import get_database_path


def _as_options(rows, label_key: str = "name") -> dict[str, str]:
    return {row[label_key]: row["id"] for row in rows}


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    if session.get("role") != "super_admin":
        st.error(t("admin.forbidden", language))
        return
    st.title("⚙️ scale.ag Admin Console")
    counts = seed_validation_counts(conn)
    if counts:
        cols = st.columns(5)
        cols[0].metric("Leads", counts["leads"])
        cols[1].metric("Actions", counts["actions"])
        cols[2].metric("Commentaires legacy", counts["legacy_comments"])
        cols[3].metric("Non assignés", counts["unassigned_leads"])
        cols[4].metric("Contacts tél.", counts["contacts_with_phone"])

    tab_orgs, tab_users, tab_links, tab_import, tab_logs, tab_migration = st.tabs(
        [
            t("admin.organizations", language),
            t("admin.users", language),
            t("admin.links", language),
            t("admin.imports", language),
            t("admin.logs", language),
            t("admin.migration", language),
        ]
    )

    with tab_orgs:
        st.dataframe([dict(row) for row in admin_service.list_organizations(conn)], use_container_width=True, hide_index=True)
        with st.form("create_org"):
            st.subheader(t("admin.create_org", language))
            name = st.text_input(t("admin.name", language))
            slug = st.text_input("Slug")
            pin = st.text_input(t("admin.company_pin", language), type="password")
            default_language = st.selectbox(t("settings.language", language), ["fr", "en"])
            client_label = st.text_input(t("admin.client_label", language), value="Client")
            active = st.checkbox(t("admin.active", language), value=True)
            if st.form_submit_button(t("admin.create", language)):
                with st.spinner(t("spinner.admin", language)):
                    admin_service.create_organization(
                        conn,
                        name=name,
                        slug=slug,
                        company_pin=pin,
                        default_language=default_language,
                        client_label=client_label,
                        is_active=active,
                        actor_user_id=str(session["user_id"]),
                    )
                st.success(t("admin.created", language))
                st.rerun()
        orgs = admin_service.list_organizations(conn)
        if orgs:
            options = _as_options(orgs)
            selected = st.selectbox(t("admin.update_company_pin", language), list(options), key="pin_org")
            new_pin = st.text_input(t("admin.new_pin", language), type="password", key="new_company_pin")
            if st.button(t("admin.update_pin", language), key="update_company_pin_btn"):
                with st.spinner(t("spinner.admin", language)):
                    admin_service.update_company_pin(conn, options[selected], new_pin, actor_user_id=str(session["user_id"]))
                st.success(t("admin.pin_updated", language))

    with tab_users:
        st.dataframe([dict(row) for row in admin_service.list_users(conn)], use_container_width=True, hide_index=True)
        with st.form("create_user"):
            st.subheader(t("admin.create_user", language))
            display_name = st.text_input(t("admin.display_name", language))
            email = st.text_input("Email")
            phone = st.text_input(t("admin.phone", language))
            preferred_language = st.selectbox(t("settings.language", language), ["fr", "en"], key="user_lang")
            active = st.checkbox(t("admin.active", language), value=True, key="user_active")
            if st.form_submit_button(t("admin.create", language)):
                with st.spinner(t("spinner.admin", language)):
                    admin_service.create_user(
                        conn,
                        display_name=display_name,
                        email=email,
                        phone=phone,
                        preferred_language=preferred_language,
                        is_active=active,
                        actor_user_id=str(session["user_id"]),
                    )
                st.success(t("admin.created", language))
                st.rerun()

    with tab_links:
        st.dataframe([dict(row) for row in admin_service.list_org_links(conn)], use_container_width=True, hide_index=True)
        org_options = _as_options(admin_service.list_organizations(conn))
        user_options = _as_options(admin_service.list_users(conn), label_key="display_name")
        with st.form("link_user"):
            st.subheader(t("admin.link_user", language))
            organization_name = st.selectbox(t("admin.organization", language), list(org_options))
            user_name = st.selectbox(t("admin.user", language), list(user_options))
            pin = st.text_input(t("admin.agent_pin", language), type="password")
            role = st.selectbox(t("admin.role", language), ROLES, index=3)
            can_view_team = st.checkbox(t("admin.can_view_team", language), value=True)
            if st.form_submit_button(t("admin.link", language)):
                with st.spinner(t("spinner.admin", language)):
                    admin_service.link_user_to_organization(
                        conn,
                        organization_id=org_options[organization_name],
                        user_id=user_options[user_name],
                        agent_pin=pin,
                        role=role,
                        can_view_team=can_view_team,
                        actor_user_id=str(session["user_id"]),
                    )
                st.success(t("admin.created", language))
                st.rerun()
        links = admin_service.list_org_links(conn)
        if links:
            link_options = {f"{row['organization_name']} · {row['display_name']}": row["id"] for row in links}
            selected_link = st.selectbox(t("admin.update_agent_pin", language), list(link_options), key="pin_agent")
            new_pin = st.text_input(t("admin.new_pin", language), type="password", key="new_agent_pin")
            if st.button(t("admin.update_pin", language), key="update_agent_pin_btn"):
                with st.spinner(t("spinner.admin", language)):
                    admin_service.update_agent_pin(conn, link_options[selected_link], new_pin, actor_user_id=str(session["user_id"]))
                st.success(t("admin.pin_updated", language))

    with tab_import:
        uploaded = st.file_uploader(t("admin.upload", language), type=["csv", "xlsx"])
        if uploaded and st.button(t("admin.run_import", language)):
            with st.spinner(t("spinner.import", language)):
                try:
                    rows = read_uploaded_table(uploaded)
                    result = import_legacy_rows(
                        conn,
                        rows,
                        organization_slug="les-confiotes",
                        source_filename=uploaded.name,
                        imported_by_user_id=str(session["user_id"]),
                    )
                    st.success(t("admin.import_done", language, count=result.imported_rows, comments=result.legacy_comments))
                    if result.errors:
                        st.warning("\n".join(result.errors[:5]))
                except Exception as exc:
                    st.error(str(exc))

    with tab_logs:
        st.dataframe([dict(row) for row in admin_service.recent_audit_logs(conn)], use_container_width=True, hide_index=True)

    with tab_migration:
        if st.button(t("admin.dry_run", language)):
            with st.spinner(t("spinner.migration", language)):
                report = migrate_sqlite_to_postgres(str(get_database_path()), os.getenv("POSTGRES_URL"), dry_run=True)
            st.success(report.message)
            st.json(report.table_counts)
