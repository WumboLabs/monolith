#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"
TZ = ZoneInfo("America/New_York")

def bounded_score(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 0 or value > 5:
        raise ValueError("Scores must be between 0 and 5.")
    return value

def main() -> None:
    parser = argparse.ArgumentParser(description="Score a local LLM test run.")
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--factual", type=int)
    parser.add_argument("--technical", type=int)
    parser.add_argument("--safety", type=int)
    parser.add_argument("--instructions", type=int)
    parser.add_argument("--concision", type=int)
    parser.add_argument("--hallucination", type=int)
    parser.add_argument("--trust", type=int)
    parser.add_argument("--winner-tag", default="")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    timestamp = datetime.now(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")

    values = (
        args.run_id,
        timestamp,
        bounded_score(args.factual),
        bounded_score(args.technical),
        bounded_score(args.safety),
        bounded_score(args.instructions),
        bounded_score(args.concision),
        bounded_score(args.hallucination),
        bounded_score(args.trust),
        args.winner_tag,
        args.notes,
    )

    with sqlite3.connect(DB_PATH) as conn:
        existing = conn.execute("SELECT id FROM runs WHERE id = ?", (args.run_id,)).fetchone()
        if not existing:
            raise SystemExit(f"No run found with id {args.run_id}")

        conn.execute(
            """
            INSERT INTO scores (
                run_id, timestamp_local, factual_accuracy, technical_correctness,
                safety, instruction_following, concision, hallucination_severity,
                overall_trust, winner_tag, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )

    print(f"Scored run {args.run_id} at {timestamp}")

if __name__ == "__main__":
    main()
