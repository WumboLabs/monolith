#!/usr/bin/env python3

from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"

with sqlite3.connect(DB_PATH) as conn:
    rows = conn.execute(
        """
        SELECT id, timestamp_local, launcher, model_display_name, prompt_category, generation_tps, notes
        FROM runs
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

if not rows:
    print("No runs logged yet.")
else:
    for row in rows:
        print(row)
