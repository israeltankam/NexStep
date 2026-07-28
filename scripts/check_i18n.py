"""Audit NexStep translation keys and formatting placeholders.

The audit checks literal calls to ``t()``, known runtime-generated keys,
French/English catalog parity, and placeholder parity. It does not modify any
file and returns a non-zero exit code when a visible raw key could occur.
"""

from __future__ import annotations

import ast
import json
import string
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATHS = {
    "fr": ROOT / "locales" / "fr.json",
    "en": ROOT / "locales" / "en.json",
}
SOURCE_PATHS = [
    ROOT / "app.py",
    *sorted((ROOT / "components").glob("*.py")),
    *sorted((ROOT / "pages").glob("*.py")),
    *sorted((ROOT / "services").glob("*.py")),
    *sorted((ROOT / "utils").glob("*.py")),
]

# These keys are assembled with f-strings at runtime and cannot be fully
# discovered by a literal-only AST scan.
DYNAMIC_KEYS = {
    *(f"login.{mode}_hello" for mode in ("login", "setup", "change")),
    *(f"guided.outcome.{value}" for value in ("interested", "callback", "unavailable", "refusal")),
    *(f"guided.action.{value}" for value in ("call", "message", "visit", "meeting", "none")),
    *(f"delay.{value}" for value in ("today", "tomorrow", "3", "7", "14", "30", "custom", "none")),
    *(f"urgency.{value}" for value in ("red", "yellow", "green", "blue", "gray")),
    *(
        f"board.action.status.{value}"
        for value in ("pending", "completed", "cancelled", "done", "transferred")
    ),
}

# Service results passed to t() through variables rather than string literals.
RUNTIME_MESSAGE_KEYS = {
    "login.invalid_credentials",
    "login.too_many_attempts",
    "quick_access.invalid",
    "quick_access.expired",
    "quick_access.success",
}


def _literal_translation_keys(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "t":
            continue
        first_argument = node.args[0]
        if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
            keys.add(first_argument.value)
    return keys


def _placeholders(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(template)
        if field_name
    }


def main() -> int:
    catalogs = {
        language: json.loads(path.read_text(encoding="utf-8"))
        for language, path in CATALOG_PATHS.items()
    }
    required = set(DYNAMIC_KEYS) | set(RUNTIME_MESSAGE_KEYS)
    for path in SOURCE_PATHS:
        required.update(_literal_translation_keys(path))

    errors: list[str] = []
    for language, catalog in catalogs.items():
        missing = sorted(required - set(catalog))
        if missing:
            errors.append(f"{language}: missing keys: {', '.join(missing)}")

    parity_difference = set(catalogs["fr"]) ^ set(catalogs["en"])
    if parity_difference:
        errors.append(f"FR/EN key mismatch: {', '.join(sorted(parity_difference))}")

    for key in sorted(set(catalogs["fr"]) & set(catalogs["en"])):
        fr_fields = _placeholders(str(catalogs["fr"][key]))
        en_fields = _placeholders(str(catalogs["en"][key]))
        if fr_fields != en_fields:
            errors.append(
                f"{key}: placeholder mismatch FR={sorted(fr_fields)} EN={sorted(en_fields)}"
            )

    if errors:
        print("NexStep i18n audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"NexStep i18n audit OK: {len(required)} used/runtime keys, "
        f"{len(catalogs['fr'])} catalog entries per language."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
