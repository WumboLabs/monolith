#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("America/New_York")

PROMPT_ROOT = ROOT / "prompts" / "daily-eval"
RESPONSE_ROOT = ROOT / "runs" / "responses"
LOG_SCRIPT = ROOT / "scripts" / "log_manual_run.py"
SHOW_LATEST = ROOT / "scripts" / "show_latest.py"

MODEL_PRESETS = {
    "gemma4-q5": {
        "launcher": "lgemma",
        "model_key": "gemma4_12b_it_ud_q5_k_xl",
        "model_name": "Gemma 4 12B IT UD-Q5_K_XL",
        "family": "Gemma 4",
        "quant": "UD-Q5_K_XL",
        "profile": "daily_eval",
        "ctx": "8192",
        "cache_k": "f16",
        "cache_v": "f16",
        "generation_tps": "57.2",
        "response_dir": "gemma4-12b-ud-q5",
    },
    "gemma4-q5-16k": {
        "launcher": "lgemma16k",
        "model_key": "gemma4_12b_it_ud_q5_k_xl",
        "model_name": "Gemma 4 12B IT UD-Q5_K_XL",
        "family": "Gemma 4",
        "quant": "UD-Q5_K_XL",
        "profile": "gemma4_q5_16k",
        "ctx": "16384",
        "cache_k": "f16",
        "cache_v": "f16",
        "generation_tps": "59.5",
        "response_dir": "gemma4-12b-ud-q5",
    },
    "gemma4-q5-24k": {
        "launcher": "lgemma24k",
        "model_key": "gemma4_12b_it_ud_q5_k_xl",
        "model_name": "Gemma 4 12B IT UD-Q5_K_XL",
        "family": "Gemma 4",
        "quant": "UD-Q5_K_XL",
        "profile": "gemma4_q5_24k",
        "ctx": "24576",
        "cache_k": "f16",
        "cache_v": "f16",
        "generation_tps": "58.3",
        "response_dir": "gemma4-12b-ud-q5",
    },
    "qwen35": {
        "launcher": "lmoeai",
        "model_key": "qwen3_6_35b_a3b_ud_iq2_m",
        "model_name": "Qwen3.6-35B-A3B UD-IQ2_M",
        "family": "Qwen3.6",
        "quant": "UD-IQ2_M",
        "profile": "production_8k",
        "ctx": "8192",
        "cache_k": "f16",
        "cache_v": "f16",
        "generation_tps": "140",
        "response_dir": "qwen35-baseline",
    },
}

def slugify(text: str) -> str:
    cleaned = []
    for char in text.lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in (" ", "-", "_"):
            cleaned.append("-")
    slug = "".join(cleaned)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "daily-note"

def open_editor(path: Path) -> None:
    editor = os.environ.get("EDITOR") or "nvim"
    result = subprocess.run([editor, str(path)])
    if result.returncode != 0:
        raise SystemExit(f"Editor exited with code {result.returncode}")

def nonempty_file(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""

def main() -> None:
    parser = argparse.ArgumentParser(description="Editor-based daily local LLM testbench logger.")
    parser.add_argument("--model", choices=MODEL_PRESETS.keys(), default="gemma4-q5")
    parser.add_argument("--category", default="daily-eval")
    parser.add_argument("--title", default=None)
    parser.add_argument("--notes", default="")
    parser.add_argument("--generation-tps", default=None)
    parser.add_argument("--no-edit", action="store_true", help="Do not open editor; log existing generated files.")
    args = parser.parse_args()

    if not args.title:
        entered_title = input("Title for this log entry: ").strip()
        if not entered_title:
            raise SystemExit("A title is required.")
        args.title = entered_title

    preset = MODEL_PRESETS[args.model]
    timestamp = datetime.now(TZ)
    stamp = timestamp.strftime("%Y-%m-%d %I:%M %p %Z")
    date_slug = timestamp.strftime("%Y-%m-%d-%H%M")
    title_slug = slugify(args.title)
    file_stem = f"{date_slug}-{title_slug}"

    prompt_dir = PROMPT_ROOT / preset["response_dir"]
    response_dir = RESPONSE_ROOT / preset["response_dir"] / "daily"

    prompt_dir.mkdir(parents=True, exist_ok=True)
    response_dir.mkdir(parents=True, exist_ok=True)

    prompt_path = prompt_dir / f"{file_stem}.md"
    response_path = response_dir / f"{file_stem}.md"

    prompt_template = f"""# {stamp} {args.title}

## Category

{args.category}

## Prompt

PASTE EXACT PROMPT HERE
"""

    response_template = f"""# {stamp} {args.title}

## Model

{preset["model_name"]}

## Launcher

{preset["launcher"]}

## Response

PASTE MODEL RESPONSE HERE
"""

    if not prompt_path.exists():
        prompt_path.write_text(prompt_template, encoding="utf-8")

    if not response_path.exists():
        response_path.write_text(response_template, encoding="utf-8")

    if not args.no_edit:
        print()
        print(f"Opening prompt file: {prompt_path.relative_to(ROOT)}")
        open_editor(prompt_path)

        print()
        print(f"Opening response file: {response_path.relative_to(ROOT)}")
        open_editor(response_path)

    prompt_text = prompt_path.read_text(encoding="utf-8")
    response_text = response_path.read_text(encoding="utf-8")

    if "PASTE EXACT PROMPT HERE" in prompt_text or not nonempty_file(prompt_path):
        raise SystemExit("Prompt file still contains placeholder text. Aborting without logging.")

    if "PASTE MODEL RESPONSE HERE" in response_text or not nonempty_file(response_path):
        raise SystemExit("Response file still contains placeholder text. Aborting without logging.")

    gen_tps = args.generation_tps or preset["generation_tps"]

    cmd = [
        str(LOG_SCRIPT),
        "--launcher", preset["launcher"],
        "--model-key", preset["model_key"],
        "--model-name", preset["model_name"],
        "--family", preset["family"],
        "--quant", preset["quant"],
        "--profile", preset["profile"],
        "--ctx", preset["ctx"],
        "--cache-k", preset["cache_k"],
        "--cache-v", preset["cache_v"],
        "--prompt-file", str(prompt_path.relative_to(ROOT)),
        "--response-file", str(response_path.relative_to(ROOT)),
        "--category", args.category,
        "--generation-tps", gen_tps,
        "--notes", args.notes or f"Daily evaluation: {args.title}",
    ]

    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode != 0:
        print("Failed to log run.", file=sys.stderr)
        sys.exit(result.returncode)

    print()
    print("Saved:")
    print(f"Prompt:   {prompt_path.relative_to(ROOT)}")
    print(f"Response: {response_path.relative_to(ROOT)}")

    if SHOW_LATEST.exists():
        print()
        print("Latest runs:")
        subprocess.run([str(SHOW_LATEST)], cwd=ROOT)

if __name__ == "__main__":
    main()
