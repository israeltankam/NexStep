"""Reusable Streamlit presentation helpers."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st

from services.comment_service import comment_badge
from utils.dates import format_date
from utils.text import truncate


URGENCY_STYLES = {
    "red": ("#b42318", "#fff1f0"),
    "yellow": ("#b7791f", "#fff8db"),
    "green": ("#087443", "#e7f8ef"),
    "blue": ("#155eef", "#edf4ff"),
    "gray": ("#667085", "#f2f4f7"),
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; max-width: 1180px; }
        [data-testid="stSidebar"] { background: #fbfcfd; border-right: 1px solid #e5e7eb; }
        .nex-card {
            border: 1px solid #d7dee8;
            border-radius: 8px;
            padding: 18px;
            background: #ffffff;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
            margin-bottom: 14px;
        }
        .nex-muted { color: #667085; font-size: 0.92rem; }
        .nex-section-title { font-weight: 700; font-size: 1rem; margin: 0 0 8px 0; }
        .nex-focus-card {
            border: 1px solid #cfd8e5;
            border-radius: 8px;
            padding: 20px;
            background: #ffffff;
            box-shadow: 0 2px 5px rgba(16, 24, 40, 0.06);
            margin: 12px 0 14px 0;
        }
        .nex-focus-card h2 {
            font-size: 1.65rem;
            line-height: 1.2;
            margin: 12px 0 5px 0;
            letter-spacing: 0;
            overflow-wrap: anywhere;
        }
        .nex-focus-action {
            color: #172033;
            font-size: 1.1rem;
            font-weight: 700;
            margin: 0 0 14px 0;
            overflow-wrap: anywhere;
        }
        .nex-focus-meta {
            color: #526071;
            display: flex;
            flex-wrap: wrap;
            gap: 8px 22px;
            font-size: 0.94rem;
        }
        .nex-contact-link {
            color: #087443;
            font-weight: 700;
            text-decoration: none;
        }
        .nex-contact-link:hover { text-decoration: underline; }
        .nex-latest-note {
            border-left: 3px solid #12b76a;
            background: #f2fbf6;
            border-radius: 6px;
            color: #344054;
            margin: 0 0 14px 0;
            padding: 10px 12px;
            overflow-wrap: anywhere;
        }
        .nex-comment {
            border-left: 3px solid #12b76a;
            padding: 8px 10px;
            margin: 8px 0;
            background: #f6fef9;
            border-radius: 6px;
        }
        .nex-badge {
            display: inline-block;
            border-radius: 999px;
            padding: 2px 8px;
            font-size: 0.78rem;
            font-weight: 650;
            margin-right: 6px;
        }
        .nex-logo-caption { text-align:center; color:#667085; font-weight:600; margin-top:-8px; }
        .nex-sidebar-logo {
            padding: 8px 6px 2px 6px;
            margin: 0 0 6px 0;
            overflow: visible;
        }
        .nex-sidebar-logo img {
            display: block;
            width: 100%;
            max-height: 104px;
            object-fit: contain;
            object-position: center center;
        }
        .nex-login-logo {
            padding: 10px 0 4px 0;
            text-align: center;
            overflow: visible;
        }
        .nex-login-logo img {
            width: min(280px, 82vw);
            max-height: 130px;
            object-fit: contain;
            object-position: center center;
        }
        .nex-scale-logo-link {
            display: inline-block;
            padding: 4px 0;
        }
        .nex-scale-logo-link img {
            display: block;
            width: 110px;
            max-height: 68px;
            object-fit: contain;
            object-position: left center;
        }
        .nex-scale-logo-link:focus-visible {
            outline: 2px solid #087443;
            outline-offset: 3px;
            border-radius: 4px;
        }
        div[data-testid="stButton"] button {
            border-radius: 6px;
            min-height: 2.8rem;
            white-space: normal;
        }
        div[data-testid="stFormSubmitButton"] button {
            border-radius: 6px;
            min-height: 2.8rem;
            white-space: normal;
        }
        [data-testid="stProgress"] { margin: 4px 0 14px 0; }
        [data-testid="stSidebarNav"] { display: none; }
        @media (max-width: 640px) {
            .block-container { padding: 1rem 0.85rem 2rem; }
            .nex-focus-card { padding: 16px; }
            .nex-focus-card h2 { font-size: 1.4rem; }
            .nex-focus-meta { display: grid; gap: 6px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def urgency_badge(color: str, label: str | None = None) -> str:
    fg, bg = URGENCY_STYLES.get(color, URGENCY_STYLES["gray"])
    return f"<span class='nex-badge' style='color:{fg}; background:{bg};'>{label or color}</span>"


def image_data_uri(path: Path) -> str:
    """Embed local images in Streamlit HTML without relying on layout-cropping widgets."""

    suffix = path.suffix.lower().lstrip(".") or "png"
    mime = "jpeg" if suffix in {"jpg", "jpeg"} else suffix
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{mime};base64,{payload}"


def render_action_card(action: dict | object, *, urgency_label: str) -> None:
    row = dict(action)
    urgency = row.get("urgency_color") or row.get("urgency_color_cache") or "gray"
    st.markdown(
        f"""
        <div class="nex-card">
          {urgency_badge(str(urgency), urgency_label)}
          <h2 style="margin:8px 0 2px 0;">{row.get('lead_name')}</h2>
          <div class="nex-muted">{row.get('stage_name') or '—'} · {row.get('status_name') or '—'} · Score {row.get('score') or 0:g}</div>
          <p style="font-size:1.08rem;"><strong>{row.get('title')}</strong></p>
          <div class="nex-muted">Échéance: {format_date(row.get('due_date'))} · Contact: {row.get('contact_name') or '—'} · Canal: {row.get('channel_notes') or '—'}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_comments(
    comments,
    *,
    max_preview: int = 220,
    empty_label: str = "Aucun commentaire visible.",
) -> None:
    if not comments:
        st.caption(empty_label)
        return
    for comment in comments:
        created_at = html.escape(str(comment["created_at"] or "")[:16])
        author = html.escape(str(comment["author_name"] or "NexStep"))
        badge = html.escape(comment_badge(comment))
        body = html.escape(truncate(str(comment["body"] or ""), max_preview))
        st.markdown(
            f"""
            <div class="nex-comment">
              <div>{urgency_badge('green', badge)}
              <span class="nex-muted">{created_at} · {author}</span></div>
              <div>{body}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
