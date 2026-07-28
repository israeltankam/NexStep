"""scale.ag admin console."""

from __future__ import annotations

import os
import sqlite3

import streamlit as st

from services import admin_service
from services.import_service import import_legacy_rows, read_uploaded_table
from services.migration_service import migrate_sqlite_to_postgres
from services.organization_data_service import (
    export_organization_csv_archive,
    parse_organization_csv_archive,
    replace_organization_business_data,
    verify_replacement_authorization,
)
from services.password_reset_service import list_pending_requests, review_password_reset
from services.seed_service import seed_validation_counts
from utils.constants import ROLES
from utils.i18n import t
from utils.paths import get_database_path


def _as_options(rows, label_key: str = "name") -> dict[str, str]:
    return {row[label_key]: row["id"] for row in rows}


def _render_password_resets(
    conn: sqlite3.Connection,
    session: dict[str, object],
    language: str,
) -> None:
    """Render the company administrator's in-app reset inbox."""

    requests = list_pending_requests(conn, str(session["organization_id"]))
    if not requests:
        st.success(t("password_reset.admin_empty", language))
        return
    for request in requests:
        st.markdown(f"**{request['display_name']}**")
        st.caption(t("password_reset.request_date", language, date=request["requested_at"]))
        approve_col, reject_col = st.columns(2)
        if approve_col.button(
            t("password_reset.approve", language),
            key=f"approve_reset_{request['id']}",
            type="primary",
            use_container_width=True,
        ):
            with st.spinner(t("password_reset.review_spinner", language)):
                review_password_reset(
                    conn,
                    request_id=str(request["id"]),
                    organization_id=str(session["organization_id"]),
                    reviewer_user_id=str(session["user_id"]),
                    approve=True,
                )
            st.success(t("password_reset.approved", language))
            st.rerun()
        if reject_col.button(
            t("password_reset.reject", language),
            key=f"reject_reset_{request['id']}",
            use_container_width=True,
        ):
            with st.spinner(t("password_reset.review_spinner", language)):
                review_password_reset(
                    conn,
                    request_id=str(request["id"]),
                    organization_id=str(session["organization_id"]),
                    reviewer_user_id=str(session["user_id"]),
                    approve=False,
                )
            st.success(t("password_reset.rejected", language))
            st.rerun()


def _render_company_data(
    conn: sqlite3.Connection,
    session: dict[str, object],
    language: str,
) -> None:
    """Export or carefully replace one company's relational CSV archive."""

    organization_id = str(session["organization_id"])
    st.subheader(t("company_data.export_title", language))
    st.caption(t("company_data.export_hint", language))
    if st.button(
        t("company_data.prepare_export", language),
        key="prepare_company_export",
        use_container_width=True,
    ):
        with st.spinner(t("company_data.export_spinner", language)):
            st.session_state["company_export_archive"] = export_organization_csv_archive(
                conn,
                organization_id,
            )
    if archive := st.session_state.get("company_export_archive"):
        st.download_button(
            t("company_data.download", language),
            archive,
            file_name="nexstep_donnees_entreprise_csv.zip",
            mime="application/zip",
            use_container_width=True,
        )

    st.divider()
    st.subheader(t("company_data.replace_title", language))
    st.warning(t("company_data.replace_warning", language))
    uploaded = st.file_uploader(
        t("company_data.upload", language),
        type=["zip"],
        key="company_data_upload",
    )
    if not uploaded:
        return
    try:
        archive_data = parse_organization_csv_archive(uploaded.getvalue(), organization_id)
    except ValueError as exc:
        st.error(t("company_data.invalid_archive", language, reason=str(exc)))
        return

    total_rows = sum(len(rows) for rows in archive_data.values())
    st.info(t("company_data.valid_archive", language, count=total_rows))
    with st.form("replace_company_data_confirmation"):
        pin_1 = st.text_input(t("company_data.pin_1", language), type="password")
        pin_2 = st.text_input(t("company_data.pin_2", language), type="password")
        pin_3 = st.text_input(t("company_data.pin_3", language), type="password")
        password = st.text_input(t("company_data.password", language), type="password")
        submitted = st.form_submit_button(
            t("company_data.replace_button", language),
            type="primary",
            use_container_width=True,
        )
    if not submitted:
        return
    if not verify_replacement_authorization(
        conn,
        organization_id=organization_id,
        user_id=str(session["user_id"]),
        company_pins=(pin_1, pin_2, pin_3),
        password=password,
    ):
        st.error(t("company_data.authorization_failed", language))
        return
    with st.spinner(t("company_data.replace_spinner", language)):
        replace_organization_business_data(
            conn,
            organization_id=organization_id,
            actor_user_id=str(session["user_id"]),
            archive_data=archive_data,
        )
    st.session_state.pop("company_export_archive", None)
    st.success(t("company_data.replaced", language))
    st.rerun()


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    role = str(session.get("role") or "")
    if role not in {"super_admin", "company_admin"}:
        st.error(t("admin.forbidden", language))
        return
    st.title("⚙️ " + t("admin.title", language))

    if role == "company_admin":
        reset_tab, company_data_tab = st.tabs(
            [
                t("password_reset.admin_tab", language),
                t("company_data.tab", language),
            ]
        )
        with reset_tab:
            _render_password_resets(conn, session, language)
        with company_data_tab:
            _render_company_data(conn, session, language)
        return

    counts = seed_validation_counts(conn)
    if counts:
        cols = st.columns(5)
        cols[0].metric("Leads", counts["leads"])
        cols[1].metric("Actions", counts["actions"])
        cols[2].metric("Commentaires legacy", counts["legacy_comments"])
        cols[3].metric("Non assignés", counts["unassigned_leads"])
        cols[4].metric("Contacts tél.", counts["contacts_with_phone"])

    (
        tab_orgs,
        tab_users,
        tab_links,
        tab_import,
        tab_logs,
        tab_migration,
        tab_resets,
        tab_company_data,
    ) = st.tabs(
        [
            t("admin.organizations", language),
            t("admin.users", language),
            t("admin.links", language),
            t("admin.imports", language),
            t("admin.logs", language),
            t("admin.migration", language),
            t("password_reset.admin_tab", language),
            t("company_data.tab", language),
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

    with tab_resets:
        _render_password_resets(conn, session, language)

    with tab_company_data:
        _render_company_data(conn, session, language)
