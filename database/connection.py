"""Database connections for local SQLite and persistent cloud PostgreSQL.

The business services deliberately keep SQLite's ``?`` placeholders because
they are concise and already used throughout the project. The PostgreSQL
adapter translates only placeholders found outside SQL string literals, then
delegates every operation to Psycopg with dictionary-shaped rows.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from utils.paths import ensure_runtime_dirs, get_database_path


class DatabaseConfigurationError(RuntimeError):
    """Raised when cloud mode could silently fall back to ephemeral SQLite."""


class DatabaseConnectionError(RuntimeError):
    """Raised when PostgreSQL cannot be reached without exposing credentials."""


def normalize_postgres_url(database_url: str) -> str:
    """Return a Psycopg-compatible URL while preserving connection details."""

    normalized = database_url.strip()
    if normalized.startswith("postgresql+psycopg://"):
        return normalized.replace("postgresql+psycopg://", "postgresql://", 1)
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql://", 1)
    if not normalized.startswith("postgresql://"):
        raise DatabaseConfigurationError("DATABASE_URL must be a PostgreSQL URL.")
    return normalized


def adapt_query_for_postgres(query: str) -> str:
    """Translate qmark placeholders without touching question marks in strings.

    SQL identifiers and string literals can legally contain ``?``. A small
    state machine is therefore safer than a global ``str.replace``.
    """

    translated: list[str] = []
    in_single_quote = False
    in_double_quote = False
    index = 0
    while index < len(query):
        character = query[index]
        next_character = query[index + 1] if index + 1 < len(query) else ""

        if character == "'" and not in_double_quote:
            translated.append(character)
            if in_single_quote and next_character == "'":
                translated.append(next_character)
                index += 2
                continue
            in_single_quote = not in_single_quote
        elif character == '"' and not in_single_quote:
            translated.append(character)
            if in_double_quote and next_character == '"':
                translated.append(next_character)
                index += 2
                continue
            in_double_quote = not in_double_quote
        elif character == "?" and not in_single_quote and not in_double_quote:
            translated.append("%s")
        else:
            translated.append(character)
        index += 1

    return "".join(translated)


class PostgresConnection:
    """Minimal compatibility adapter used by the existing service layer."""

    backend = "postgresql"

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def execute(self, query: str, params: Sequence[object] = ()) -> Any:
        return self._connection.execute(adapt_query_for_postgres(query), tuple(params))

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


def _cloud_mode_enabled() -> bool:
    return os.getenv("APP_ENV", "").strip().casefold() in {"cloud", "production", "prod"}


def _connect_postgres(database_url: str) -> PostgresConnection:
    """Open a secure Supabase/PostgreSQL connection with pooler-safe settings."""

    try:
        import psycopg
        from psycopg.rows import dict_row

        raw_connection = psycopg.connect(
            normalize_postgres_url(database_url),
            row_factory=dict_row,
            prepare_threshold=None,
            connect_timeout=10,
            sslmode="require",
            application_name="NexStep",
        )
    except DatabaseConfigurationError:
        raise
    except Exception as exc:
        # Some drivers echo connection strings, so the public error is generic.
        raise DatabaseConnectionError("Unable to connect to PostgreSQL.") from exc
    return PostgresConnection(raw_connection)


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection | PostgresConnection:
    """Return PostgreSQL in deployed environments and SQLite for local work.

    Passing ``db_path`` explicitly always selects SQLite; this is used by tests
    and local maintenance scripts. Normal application calls prefer
    ``DATABASE_URL`` and fail closed when ``APP_ENV`` declares a cloud runtime.
    """

    if db_path is None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            return _connect_postgres(database_url)
        if _cloud_mode_enabled():
            raise DatabaseConfigurationError("DATABASE_URL is required in cloud mode.")

    path = Path(db_path) if db_path else get_database_path()
    ensure_runtime_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def transaction(conn: Any) -> Iterator[Any]:
    """Commit or roll back a group of writes as one business operation."""

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
