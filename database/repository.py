"""Tiny repository helpers that keep SQL call sites readable."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence


def fetch_one(conn: sqlite3.Connection, query: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
    return conn.execute(query, params).fetchone()


def fetch_all(conn: sqlite3.Connection, query: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(query, params).fetchall())


def insert(conn: sqlite3.Connection, table: str, values: Mapping[str, object]) -> None:
    columns = list(values.keys())
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
        [values[column] for column in columns],
    )


def update_by_id(conn: sqlite3.Connection, table: str, row_id: str, values: Mapping[str, object]) -> None:
    assignments = ", ".join(f"{column} = ?" for column in values)
    conn.execute(
        f"UPDATE {table} SET {assignments} WHERE id = ?",
        [*values.values(), row_id],
    )
