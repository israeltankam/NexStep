"""Text helpers for labels, searches, and duplicate detection."""

from __future__ import annotations

import re
import unicodedata
import uuid


def normalize_name(value: str | None) -> str:
    """Normalize names for search and duplicate groups while preserving source text elsewhere."""

    if not value:
        return ""
    without_accents = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(ch for ch in without_accents if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", ascii_only.casefold()).strip()


def slugify(value: str) -> str:
    """Create a small, readable slug suitable for organization and duplicate keys."""

    return re.sub(r"[^a-z0-9]+", "-", normalize_name(value)).strip("-")


def stable_id(kind: str, value: str | int) -> str:
    """Generate deterministic UUIDs for seed rows so repeated seeds stay idempotent."""

    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"nexstep:{kind}:{value}"))


def new_id() -> str:
    """Generate a fresh UUID for user-created records."""

    return str(uuid.uuid4())


def truncate(value: str | None, limit: int = 180) -> str:
    """Return a readable preview without hiding that longer content exists."""

    if not value:
        return ""
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - 1)].rstrip() + "…"
