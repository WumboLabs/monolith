#!/usr/bin/env python3
"""
Create additive LLMGauge import tables for Monolith.

This migration is intentionally additive. It does not modify, rename, or drop
legacy Quant Lab, context scaling, Hermes Eval, or Agent Lab tables.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


def migrate(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llmgauge_artifact_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                artifact_type TEXT NOT NULL CHECK (artifact_type IN ('run', 'ladder')),
                source_path TEXT NOT NULL,
                source_path_kind TEXT NOT NULL CHECK (source_path_kind IN ('directory', 'index_item')),
                source_hash TEXT,
                schema_version TEXT,
                imported_at_utc TEXT NOT NULL,
                validation_checked INTEGER NOT NULL DEFAULT 0,
                validation_status TEXT NOT NULL DEFAULT 'unknown'
                    CHECK (validation_status IN ('valid', 'invalid', 'unknown')),
                validation_errors_json TEXT NOT NULL DEFAULT '[]',
                artifact_json TEXT NOT NULL DEFAULT '{}',
                result_json_path TEXT,
                report_path TEXT,
                ladder_summary_path TEXT,
                ladder_report_path TEXT,
                raw_dir_path TEXT,
                logs_dir_path TEXT,
                UNIQUE(source_path, artifact_type)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llmgauge_run_summaries (
                import_id INTEGER PRIMARY KEY,
                run_id TEXT,
                status TEXT,
                timestamp_utc TEXT,
                suite_id TEXT,
                suite_version TEXT,
                model_id TEXT,
                model_profile_json TEXT NOT NULL DEFAULT '{}',
                prompt_count INTEGER,
                completed INTEGER,
                failed INTEGER,
                manual_score_total REAL,
                manual_score_max REAL,
                has_raw_artifacts INTEGER NOT NULL DEFAULT 0,
                has_logs INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(import_id)
                    REFERENCES llmgauge_artifact_imports(id)
                    ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llmgauge_ladder_summaries (
                import_id INTEGER PRIMARY KEY,
                ladder_id TEXT,
                suite_id TEXT,
                model_id TEXT,
                include_json TEXT NOT NULL DEFAULT '[]',
                only_json TEXT NOT NULL DEFAULT '[]',
                contexts_json TEXT NOT NULL DEFAULT '[]',
                child_run_count INTEGER,
                completed INTEGER,
                failed INTEGER,
                total INTEGER,
                has_child_runs INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(import_id)
                    REFERENCES llmgauge_artifact_imports(id)
                    ON DELETE CASCADE
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llmgauge_artifact_imports_type
            ON llmgauge_artifact_imports(artifact_type)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llmgauge_artifact_imports_validation
            ON llmgauge_artifact_imports(validation_status)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llmgauge_run_summaries_suite_model
            ON llmgauge_run_summaries(suite_id, model_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llmgauge_ladder_summaries_suite_model
            ON llmgauge_ladder_summaries(suite_id, model_id)
            """
        )

        conn.commit()


def main() -> None:
    migrate()
    print(f"LLMGauge import tables ready: {DB_PATH}")


if __name__ == "__main__":
    main()
