"""Small JSON-backed internationalization helper."""

from __future__ import annotations

import json
from functools import lru_cache

from utils.paths import LOCALES_DIR


DEFAULT_LANGUAGE = "fr"
SUPPORTED_LANGUAGES = {"fr": "Français", "en": "English"}


@lru_cache(maxsize=16)
def _load_locale_version(selected: str, modified_at_ns: int) -> dict[str, str]:
    """Cache one exact file version and reload it after a deployment update."""

    path = LOCALES_DIR / f"{selected}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_locale(language: str) -> dict[str, str]:
    selected = language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    path = LOCALES_DIR / f"{selected}.json"
    if not path.exists():
        return {}
    return _load_locale_version(selected, path.stat().st_mtime_ns)


def t(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: object) -> str:
    """Translate a key, falling back to French and then to the key itself."""

    catalog = load_locale(language)
    template = catalog.get(key) or load_locale(DEFAULT_LANGUAGE).get(key) or key
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template
