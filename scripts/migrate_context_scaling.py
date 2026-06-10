#!/usr/bin/env python3

from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_scaling_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                model_profile_name TEXT NOT NULL,
                model_label TEXT,
                backend_label TEXT,
                quant_label TEXT,
                cache_mode TEXT NOT NULL DEFAULT 'normal',
                context_ladder_json TEXT NOT NULL,
                selected_prompts_json TEXT NOT NULL,
                temperature REAL NOT NULL DEFAULT 0.2,
                max_tokens INTEGER NOT NULL DEFAULT 800,
                status TEXT NOT NULL DEFAULT 'planned',
                notes TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS context_scaling_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_scaling_run_id INTEGER NOT NULL,
                context_size INTEGER NOT NULL,
                prompt_category TEXT,
                prompt_filename TEXT,
                prompt_label TEXT,
                output_raw TEXT,
                output_clean_preview TEXT,
                prompt_eval_tps REAL,
                generation_tps REAL,
                peak_vram_mb INTEGER,
                exit_code INTEGER,
                status TEXT NOT NULL DEFAULT 'planned',
                error_text TEXT,
                source_report_path TEXT,
                source_report_sha256 TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(context_scaling_run_id) REFERENCES context_scaling_runs(id)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_context_scaling_results_run
            ON context_scaling_results(context_scaling_run_id)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_context_scaling_results_context
            ON context_scaling_results(context_size)
            """
        )

        conn.commit()

    print(f"Context scaling tables ready: {DB_PATH}")


if __name__ == "__main__":
    main()
