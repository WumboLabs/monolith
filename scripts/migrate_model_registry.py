#!/usr/bin/env python3
"""
Monolith alpha v0.11.0 — Model Registry schema migration.

Creates local model inventory tables.

Design goals:
- additive only
- idempotent
- approved local inventory only
- no downloader behavior
- no config editing
- no model execution
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


def migrate() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS local_model_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                scan_root TEXT NOT NULL,
                local_path TEXT NOT NULL UNIQUE,
                filename TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_at TEXT,

                family_guess TEXT,
                quant_guess TEXT,
                architecture_guess TEXT,

                registered_model_key TEXT,
                registered_profile_keys_json TEXT NOT NULL DEFAULT '[]',

                status TEXT NOT NULL DEFAULT 'discovered',
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_local_model_files_path
                ON local_model_files(local_path);

            CREATE INDEX IF NOT EXISTS idx_local_model_files_filename
                ON local_model_files(filename);

            CREATE INDEX IF NOT EXISTS idx_local_model_files_family
                ON local_model_files(family_guess);

            CREATE INDEX IF NOT EXISTS idx_local_model_files_quant
                ON local_model_files(quant_guess);

            CREATE INDEX IF NOT EXISTS idx_local_model_files_status
                ON local_model_files(status);
            """
        )

        conn.commit()

    print(f"Model Registry tables ready: {DB_PATH}")


if __name__ == "__main__":
    migrate()
