"""Reusable Streamlit presentation helpers."""

from __future__ import annotations

import base64
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
        div[data-testid="stButton"] button { border-radius: 6px; }
        [data-testid="stSidebarNav"] { display: none; }
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


def render_comments(comments, *, max_preview: int = 220) -> None:
    if not comments:
        st.caption("Aucun commentaire visible.")
        return
    for comment in comments:
        st.markdown(
            f"""
            <div class="nex-comment">
              <div>{urgency_badge('green', comment_badge(comment))}
              <span class="nex-muted">{comment['created_at'][:16]} · {comment['author_name'] or 'NexStep'}</span></div>
              <div>{truncate(comment['body'], max_preview)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
