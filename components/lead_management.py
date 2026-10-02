"""Compact lead edit and reactivation controls for the Streamlit board."""

from __future__ import annotations

import streamlit as st

from database.repository import fetch_all
from services.lead_edit_service import update_lead_details
from services.lead_permissions import editable_lead
from services.reactivation_service import reactivate_lead
from utils.dates import today
from utils.i18n import t


def render(conn, session: dict, lead: dict, language: str) -> None:
    """Keep rare administrative work behind one collapsed section."""
    lead_id = str(lead["id"])
    actor_id = str(session["org_user_id"])
    try:
        editable_lead(conn, lead_id, actor_id)
    except PermissionError:
        return

    with st.expander(t("lead_manage.options", language), expanded=False):
        with st.form(f"edit_lead_{lead_id}"):
            st.caption(t("lead_manage.password_hint", language))
            name = st.text_input(t("new_lead.name", language), value=str(lead.get("name") or ""))
            city = st.text_input(t("new_lead.city", language), value=str(lead.get("city") or ""))
            context = st.text_area(t("new_lead.context", language), value=str(lead.get("context_full") or ""))
            edited_contacts = []
            for index, contact in enumerate(lead["contacts"]):
                st.markdown(f"**{t('new_lead.contact_number', language, number=index + 1)}**")
                fields = {"id": str(contact["id"])}
                for key, label in (("full_name", "new_lead.contact_name"),
                                   ("role_title", "new_lead.contact_role"),
                                   ("phone_raw", "new_lead.phone"),
                                   ("email", "new_lead.email"),
                                   ("whatsapp", "lead_manage.whatsapp"),
                                   ("channel_notes", "lead_manage.notes")):
                    fields[key] = st.text_input(t(label, language), value=str(contact.get(key) or ""),
                                                key=f"lead_edit_{lead_id}_{index}_{key}")
                edited_contacts.append(fields)
            password = st.text_input(t("lead_manage.password", language), type="password")
            save = st.form_submit_button(t("lead_manage.save", language), use_container_width=True)
        if save:
            try:
                with st.spinner(t("lead_manage.saving", language)):
                    update_lead_details(conn, lead_id=lead_id, actor_org_user_id=actor_id,
                        password=password, name=name, city=city, context_full=context,
                        contacts=edited_contacts)
            except (ValueError, PermissionError) as exc:
                st.error(t(f"lead_manage.error.{str(exc)}", language))
            else:
                st.success(t("lead_manage.saved", language))
                st.rerun()

        if lead.get("pending_action_count") or not (lead.get("churn_flag") or lead.get("actions")):
            return
        st.divider()
        st.subheader(t("lead_manage.reactivate", language))
        action_types = fetch_all(conn, "SELECT id, name FROM action_types WHERE organization_id = ? AND is_active = 1 ORDER BY position", (session["organization_id"],))
        with st.form(f"reactivate_{lead_id}"):
            reason = st.text_area(t("lead_manage.reason", language))
            title = st.text_input(t("lead_manage.action", language))
            due = st.date_input(t("lead_manage.due", language), value=today())
            choices = {str(row["name"]): str(row["id"]) for row in action_types}
            selected_type = st.selectbox(t("lead_manage.action_type", language), list(choices)) if choices else None
            submit = st.form_submit_button(t("lead_manage.reactivate_save", language), use_container_width=True)
        if submit:
            try:
                with st.spinner(t("lead_manage.saving", language)):
                    reactivate_lead(conn, lead_id=lead_id, actor_org_user_id=actor_id,
                        reason=reason, title=title, due_date=due.isoformat(),
                        action_type_id=choices.get(selected_type) if selected_type else None)
            except (ValueError, PermissionError) as exc:
                st.error(t(f"lead_manage.error.{str(exc)}", language))
            else:
                st.success(t("lead_manage.reactivated", language))
                st.rerun()
