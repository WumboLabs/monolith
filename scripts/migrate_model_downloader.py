#!/usr/bin/env python3
"""
Monolith alpha v0.11.2 — Model Downloader schema migration.

Creates controlled model download planning tables.

Design goals:
- additive only
- idempotent
- approved download root only
- no arbitrary URL textbox
- no config editing
- no model execution
- no actual download behavior in this migration
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
            CREATE TABLE IF NOT EXISTS model_download_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at TEXT,
                completed_at TEXT,

                status TEXT NOT NULL DEFAULT 'planned',

                source_type TEXT NOT NULL DEFAULT 'huggingface',
                source_repo_id TEXT NOT NULL,
                source_filename TEXT NOT NULL,
                source_url TEXT NOT NULL,

                destination_root TEXT NOT NULL,
                destination_dir TEXT NOT NULL,
                destination_path TEXT NOT NULL UNIQUE,

                filename TEXT NOT NULL,
                size_bytes INTEGER,
                expected_size_bytes INTEGER,

                family_guess TEXT,
                quant_guess TEXT,
                architecture_guess TEXT,

                local_match INTEGER NOT NULL DEFAULT 0,
                overwrite_existing INTEGER NOT NULL DEFAULT 0,

                bytes_downloaded INTEGER NOT NULL DEFAULT 0,
                error_text TEXT,
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_model_download_jobs_status
                ON model_download_jobs(status);

            CREATE INDEX IF NOT EXISTS idx_model_download_jobs_source_repo
                ON model_download_jobs(source_repo_id);

            CREATE INDEX IF NOT EXISTS idx_model_download_jobs_filename
                ON model_download_jobs(filename);

            CREATE INDEX IF NOT EXISTS idx_model_download_jobs_destination_path
                ON model_download_jobs(destination_path);
            """
        )

        conn.commit()

    print(f"Model downloader tables ready: {DB_PATH}")


if __name__ == "__main__":
    migrate()
