"""Create the local schema and seed the scale.ag admin account."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database.connection import get_connection
from services.seed_service import ensure_seed_data


if __name__ == "__main__":
    conn = get_connection()
    ensure_seed_data(conn)
    print("NexStep seed completed. Admin PIN/PIN/password initial: 0015 / 0015 / 0015")
