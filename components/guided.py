"""Small visual building blocks shared by the guided agent pages."""

from __future__ import annotations

import html
import re
from collections.abc import Sequence

import streamlit as st

from utils.dates import format_date
from utils.i18n import t
from utils.text import truncate
from utils.ui import urgency_badge


Choice = tuple[str, str, str]


def render_progress(current: int, total: int, language: str) -> None:
    """Show a compact progress indicator for one-decision-at-a-time flows."""

    st.progress(
        current / total,
        text=t("guided.progress", language, current=current, total=total),
    )


def render_choice_grid(
    choices: Sequence[Choice],
    *,
    key_prefix: str,
    columns: int = 2,
) -> str | None:
    """Render large choice buttons and return the clicked language-neutral key."""

    selected = None
    for offset in range(0, len(choices), columns):
        row = st.columns(columns)
        for index, (value, icon, label) in enumerate(choices[offset : offset + columns]):
            if row[index].button(
                f"{icon}  {label}",
                key=f"{key_prefix}_{value}",
                use_container_width=True,
            ):
                selected = value
    return selected


def render_action_focus(action: dict[str, object], urgency_label: str, language: str) -> None:
    """Display only the information needed to perform the current action."""

    urgency = str(action.get("urgency_color") or action.get("urgency_color_cache") or "gray")
    lead_name = html.escape(str(action.get("lead_name") or "—"))
    title = html.escape(str(action.get("title") or "—"))
    due_date = html.escape(format_date(action.get("due_date")))
    contact_name = html.escape(str(action.get("contact_name") or ""))
    phone = str(action.get("phone_raw") or "").strip()
    callable_phone = re.sub(r"[^0-9+]", "", phone)

    contact_parts = []
    if contact_name:
        contact_parts.append(contact_name)
    if phone:
        safe_phone = html.escape(phone)
        if callable_phone:
            contact_parts.append(
                f"<a class='nex-contact-link' href='tel:{html.escape(callable_phone)}'>"
                f"☎ {safe_phone}</a>"
            )
        else:
            contact_parts.append(safe_phone)
    contact_text = " · ".join(contact_parts) or "—"

    st.markdown(
        f"""
        <div class="nex-focus-card">
          <div>{urgency_badge(urgency, urgency_label)}</div>
          <h2>{lead_name}</h2>
          <p class="nex-focus-action">{title}</p>
          <div class="nex-focus-meta">
            <span><strong>{html.escape(t('guided.due', language))}:</strong> {due_date}</span>
            <span><strong>{html.escape(t('guided.contact', language))}:</strong> {contact_text}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_latest_note(body: str | None, language: str) -> None:
    """Keep the most useful recent context visible without showing a full log."""

    if not body:
        return
    st.markdown(
        f"<div class='nex-latest-note'><strong>{html.escape(t('guided.last_note', language))}</strong> "
        f"{html.escape(truncate(str(body), 260))}</div>",
        unsafe_allow_html=True,
    )
