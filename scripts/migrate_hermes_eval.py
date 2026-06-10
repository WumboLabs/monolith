#!/usr/bin/env python3
"""
Monolith alpha v0.09.0 — Hermes Eval schema migration.

Creates dedicated tables for Hermes Backend Eval.

Design goals:
- additive only
- idempotent
- no destructive schema changes
- no runner behavior changes
- no UI behavior changes
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
            CREATE TABLE IF NOT EXISTS hermes_eval_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                model_profile_name TEXT NOT NULL,
                model_label TEXT,
                model_path TEXT,
                model_sha256 TEXT,

                llama_cli_path TEXT,
                llama_build TEXT,

                suite_name TEXT NOT NULL DEFAULT 'hermes-v1',
                context_ladder_json TEXT NOT NULL,
                selected_prompts_json TEXT NOT NULL,

                max_tokens INTEGER NOT NULL DEFAULT 800,
                temperature REAL NOT NULL DEFAULT 0.2,
                gpu_layers INTEGER,
                cache_settings TEXT NOT NULL DEFAULT 'normal',
                reasoning_setting TEXT NOT NULL DEFAULT 'off',

                status TEXT NOT NULL DEFAULT 'planned',
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS hermes_eval_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,

                prompt_category TEXT NOT NULL,
                prompt_name TEXT NOT NULL,
                prompt_path TEXT,

                context_size INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                exit_code INTEGER,

                prompt_eval_tps REAL,
                generation_tps REAL,
                total_runtime_sec REAL,

                peak_vram_mib INTEGER,
                available_vram_mib INTEGER,
                vram_headroom_mib INTEGER,

                raw_output TEXT,
                cleaned_output TEXT,
                output_truncated INTEGER NOT NULL DEFAULT 0,

                error_text TEXT,
                source_log_path TEXT,
                source_log_sha256 TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(run_id) REFERENCES hermes_eval_runs(id)
            );

            CREATE TABLE IF NOT EXISTS hermes_eval_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                result_id INTEGER NOT NULL,

                fit_score INTEGER,
                context_score INTEGER,
                tool_honesty_score INTEGER,
                shell_safety_score INTEGER,
                coding_score INTEGER,
                ops_score INTEGER,
                output_quality_score INTEGER,
                speed_score INTEGER,
                aggregate_score REAL,

                flags_json TEXT NOT NULL DEFAULT '[]',
                scorer TEXT NOT NULL DEFAULT 'manual',
                notes TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(result_id) REFERENCES hermes_eval_results(id)
            );

            CREATE INDEX IF NOT EXISTS idx_hermes_eval_results_run
                ON hermes_eval_results(run_id);

            CREATE INDEX IF NOT EXISTS idx_hermes_eval_results_context
                ON hermes_eval_results(context_size);

            CREATE INDEX IF NOT EXISTS idx_hermes_eval_results_prompt
                ON hermes_eval_results(prompt_category, prompt_name);

            CREATE INDEX IF NOT EXISTS idx_hermes_eval_scores_result
                ON hermes_eval_scores(result_id);
            """
        )

        conn.commit()

    print(f"Hermes Eval schema migrated: {DB_PATH}")


if __name__ == "__main__":
    migrate()
