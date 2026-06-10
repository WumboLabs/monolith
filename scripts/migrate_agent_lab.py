#!/usr/bin/env python3
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row[1] for row in rows}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            goal TEXT NOT NULL,
            model_profile_name TEXT,
            model_label TEXT,
            mode TEXT NOT NULL DEFAULT 'proposal_only',
            status TEXT NOT NULL DEFAULT 'draft',
            workspace_label TEXT,
            workspace_path TEXT,
            context_summary TEXT,
            safety_notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            closed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            title TEXT,
            plan_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS agent_action_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            plan_id INTEGER,
            title TEXT NOT NULL,
            proposal_type TEXT NOT NULL DEFAULT 'note',
            body TEXT NOT NULL,
            expected_effect TEXT,
            risk_level TEXT NOT NULL DEFAULT 'unknown',
            files_affected TEXT,
            rollback_plan TEXT,
            verification_step TEXT,
            status TEXT NOT NULL DEFAULT 'proposed',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY(plan_id) REFERENCES agent_plans(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS agent_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            subject_type TEXT NOT NULL DEFAULT 'session',
            subject_id INTEGER,
            review_text TEXT NOT NULL,
            score INTEGER,
            status TEXT NOT NULL DEFAULT 'saved',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(session_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_agent_sessions_status
            ON agent_sessions(status);

        CREATE INDEX IF NOT EXISTS idx_agent_sessions_created_at
            ON agent_sessions(created_at);

        CREATE INDEX IF NOT EXISTS idx_agent_plans_session_id
            ON agent_plans(session_id);

        CREATE INDEX IF NOT EXISTS idx_agent_proposals_session_id
            ON agent_action_proposals(session_id);

        CREATE INDEX IF NOT EXISTS idx_agent_proposals_status
            ON agent_action_proposals(status);

        CREATE INDEX IF NOT EXISTS idx_agent_reviews_session_id
            ON agent_reviews(session_id);
        """
    )

    conn.commit()

    tables = [
        "agent_sessions",
        "agent_plans",
        "agent_action_proposals",
        "agent_reviews",
    ]

    print(f"Database: {DB_PATH}")
    for table in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count}")

    conn.close()


if __name__ == "__main__":
    main()
