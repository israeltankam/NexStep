"""Central paths used by the Streamlit app, tests, scripts, and services."""

from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
ASSETS_DIR = ROOT_DIR / "assets"
LOGOS_DIR = ASSETS_DIR / "logos"
LOCALES_DIR = ROOT_DIR / "locales"
DOCS_DIR = ROOT_DIR / "docs"

NEXSTEP_LOGO = LOGOS_DIR / "nexstep_logo.png"
SCALEAG_LOGO = LOGOS_DIR / "scaleag_logo.png"
USER_GUIDE_HTML = DOCS_DIR / "user_guide.html"
MIGRATION_GUIDE_HTML = DOCS_DIR / "migration_sqlite_to_postgresql_streamlit_cloud.html"


def get_database_path() -> Path:
    """Return the active SQLite path, allowing tests to isolate their database."""

    configured = os.getenv("NEXSTEP_DATABASE_PATH")
    return Path(configured) if configured else DATA_DIR / "local.db"


def ensure_runtime_dirs() -> None:
    """Create writable runtime directories without touching user data."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)
