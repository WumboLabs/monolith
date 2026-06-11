from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generated_chat_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                profile_key TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                model_path TEXT NOT NULL,
                launcher TEXT NOT NULL,
                ctx_size INTEGER NOT NULL DEFAULT 8192,
                batch_size INTEGER NOT NULL DEFAULT 256,
                ubatch_size INTEGER NOT NULL DEFAULT 64,
                gpu_layers INTEGER NOT NULL DEFAULT 999,
                temperature REAL NOT NULL DEFAULT 0.2,
                max_tokens INTEGER NOT NULL DEFAULT 800,
                reasoning TEXT NOT NULL DEFAULT 'off',
                extra_args_json TEXT NOT NULL DEFAULT '[]',
                source TEXT NOT NULL DEFAULT 'local_inventory',
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generated_chat_profiles_active
            ON generated_chat_profiles(active)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_generated_chat_profiles_model_path
            ON generated_chat_profiles(model_path)
            """
        )
        conn.commit()

    print(f"Generated chat profile tables ready: {DB_PATH}")


if __name__ == "__main__":
    main()
