#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import socket
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"
TZ = ZoneInfo("America/New_York")

def read_text(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser(description="Log a manual local LLM test run.")
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--model-key", required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--family", default="")
    parser.add_argument("--quant", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--ctx", type=int, default=None)
    parser.add_argument("--cache-k", default="")
    parser.add_argument("--cache-v", default="")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--response-file", required=True)
    parser.add_argument("--category", default="")
    parser.add_argument("--prompt-eval-tps", type=float, default=None)
    parser.add_argument("--generation-tps", type=float, default=None)
    parser.add_argument("--vram-peak-mb", type=int, default=None)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    timestamp = datetime.now(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    prompt_text = read_text(args.prompt_file)
    response_text = read_text(args.response_file)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                timestamp_local, hostname, launcher, model_key, model_display_name,
                model_family, quant, profile_name, ctx_size, cache_type_k, cache_type_v,
                prompt_file, prompt_category, prompt_text, response_text,
                prompt_eval_tps, generation_tps, vram_peak_mb,
                response_path, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                socket.gethostname(),
                args.launcher,
                args.model_key,
                args.model_name,
                args.family,
                args.quant,
                args.profile,
                args.ctx,
                args.cache_k,
                args.cache_v,
                args.prompt_file,
                args.category,
                prompt_text,
                response_text,
                args.prompt_eval_tps,
                args.generation_tps,
                args.vram_peak_mb,
                args.response_file,
                args.notes,
            ),
        )

    print(f"Logged manual run at {timestamp}")

if __name__ == "__main__":
    main()
