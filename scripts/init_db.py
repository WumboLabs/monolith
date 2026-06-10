#!/usr/bin/env python3

from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_local TEXT NOT NULL,
    hostname TEXT,
    launcher TEXT NOT NULL,
    model_key TEXT,
    model_display_name TEXT,
    model_family TEXT,
    quant TEXT,
    gguf_filename TEXT,
    llama_cpp_build TEXT,
    profile_name TEXT,
    ctx_size INTEGER,
    cache_type_k TEXT,
    cache_type_v TEXT,
    batch_size INTEGER,
    ubatch_size INTEGER,
    gpu_layers TEXT,
    reasoning TEXT,
    mmproj TEXT,
    prompt_file TEXT,
    prompt_category TEXT,
    prompt_text TEXT,
    response_text TEXT,
    prompt_tokens INTEGER,
    output_tokens INTEGER,
    prompt_eval_tps REAL,
    generation_tps REAL,
    total_wall_seconds REAL,
    vram_peak_mb INTEGER,
    exit_code INTEGER,
    raw_log_path TEXT,
    response_path TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    timestamp_local TEXT NOT NULL,
    factual_accuracy INTEGER,
    technical_correctness INTEGER,
    safety INTEGER,
    instruction_following INTEGER,
    concision INTEGER,
    hallucination_severity INTEGER,
    overall_trust INTEGER,
    winner_tag TEXT,
    notes TEXT,
    FOREIGN KEY(run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS benchmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp_local TEXT NOT NULL,
    hostname TEXT,
    benchmark_tool TEXT,
    launcher TEXT,
    model_key TEXT,
    quant TEXT,
    ctx_size INTEGER,
    cache_type_k TEXT,
    cache_type_v TEXT,
    batch_size INTEGER,
    ubatch_size INTEGER,
    prompt_eval_tps REAL,
    generation_tps REAL,
    vram_peak_mb INTEGER,
    raw_path TEXT,
    notes TEXT
);
"""

def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
    print(f"Initialized database: {DB_PATH}")

if __name__ == "__main__":
    main()
