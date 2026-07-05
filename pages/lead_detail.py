"""Lead detail page with full comment history."""

from __future__ import annotations

import json
import sqlite3

import streamlit as st

from database.repository import fetch_all
from services.comment_service import add_comment, list_comments_for_lead, search_comments
from services.lead_service import get_lead_detail, get_primary_contact, list_leads
from utils.i18n import t
from utils.ui import render_comments
from utils.urgency import urgency_label


def _lead_picker(conn: sqlite3.Connection, organization_id: str, language: str) -> str | None:
    search = st.text_input(t("lead.search", language))
    leads = list_leads(conn, organization_id, search)
    if not leads:
        st.info(t("lead.no_result", language))
        return None
    options = {f"{lead['name']} · {lead['status_name'] or '—'}": lead["id"] for lead in leads}
    selected = st.selectbox(t("lead.choose", language), list(options))
    return options[selected]


def render(conn: sqlite3.Connection, session: dict[str, object]) -> None:
    language = str(session.get("language", "fr"))
    st.title("💬 " + t("lead.title", language))
    lead_id = st.session_state.get("selected_lead_id") or _lead_picker(conn, str(session["organization_id"]), language)
    if not lead_id:
        return
    lead = get_lead_detail(conn, str(lead_id))
    if not lead:
        st.error(t("lead.not_found", language))
        return
    st.session_state["selected_lead_id"] = lead["id"]

    contact = get_primary_contact(conn, lead["id"])
    col1, col2, col3 = st.columns(3)
    col1.metric(t("lead.customer", language), lead["name"])
    col2.metric(t("lead.stage", language), lead["stage_name"] or "—")
    col3.metric(t("lead.score", language), f"{lead['score'] or 0:g}")
    st.caption(f"{lead['status_name'] or '—'} · {lead['category_name'] or '—'} · {lead['owner_name'] or t('lead.unassigned', language)}")

    with st.expander(t("lead.identity", language), expanded=True):
        st.write(
            {
                t("lead.contact", language): contact["full_name"] if contact else "—",
                t("lead.phone", language): contact["phone_raw"] if contact else "—",
                t("lead.channel", language): contact["channel_notes"] if contact else "—",
                t("lead.source", language): lead["source"] or "—",
                t("lead.city", language): lead["city"] or "—",
                t("lead.obstacle", language): lead["obstacle"] or "—",
            }
        )
    with st.expander(t("lead.context", language), expanded=False):
        st.write(lead["context_full"] or "—")
        if lead["legacy_fields_json"]:
            st.json(json.loads(lead["legacy_fields_json"]))

    st.subheader("💬 " + t("comments.history", language))
    with st.form(f"lead_comment_{lead['id']}"):
        body = st.text_area(t("comments.general_add", language), height=100)
        if st.form_submit_button("💬 " + t("comments.save", language)):
            with st.spinner(t("spinner.comment", language)):
                add_comment(
                    conn,
                    organization_id=lead["organization_id"],
                    lead_id=lead["id"],
                    org_user_id=str(session["org_user_id"]),
                    body=body,
                    comment_type="general",
                )
                conn.commit()
            st.success(t("comments.saved", language))
            st.rerun()
    render_comments(list_comments_for_lead(conn, lead["id"]), max_preview=2000)

    st.subheader("📋 " + t("lead.actions", language))
    actions = fetch_all(conn, "SELECT * FROM actions WHERE lead_id = ? ORDER BY created_at DESC", (lead["id"],))
    readable_actions = []
    for action in actions:
        row = dict(action)
        row["urgency_label"] = urgency_label(row.get("urgency_color_cache") or "gray", language)
        row.pop("urgency_color_cache", None)
        readable_actions.append(row)
    st.dataframe(readable_actions, use_container_width=True, hide_index=True)

    st.subheader("🔎 " + t("comments.search", language))
    query = st.text_input(t("comments.search_placeholder", language))
    if query:
        render_comments(search_comments(conn, str(session["organization_id"]), query), max_preview=260)
