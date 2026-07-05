"""Seed the Les Confiotes pilot data and print acceptance counts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.connection import get_connection
from services.seed_service import ensure_seed_data, seed_validation_counts


if __name__ == "__main__":
    conn = get_connection()
    ensure_seed_data(conn)
    for key, value in seed_validation_counts(conn).items():
        print(f"{key}: {value}")
