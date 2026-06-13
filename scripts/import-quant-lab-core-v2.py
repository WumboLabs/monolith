#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"


@dataclass
class PromptSection:
    prompt_order: int
    category: str
    prompt_name: str
    prompt_file: str | None
    prompt_text: str
    output_text: str
    prompt_eval_tps: float | None
    generation_tps: float | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
      for chunk in iter(lambda: handle.read(1024 * 1024), b""):
          digest.update(chunk)

    return digest.hexdigest()


def strip_code_fence(value: str) -> str:
    text = value.strip("\n")

    if text.startswith("~~~text"):
        text = text.removeprefix("~~~text").strip("\n")

    if text.endswith("~~~"):
        text = text[:-3].strip("\n")

    return text.strip("\n")


def extract_block(section: str, heading: str, following_headings: list[str]) -> str:
    start_marker = f"### {heading}"
    start = section.find(start_marker)

    if start == -1:
        return ""

    start += len(start_marker)

    end_candidates = []
    for next_heading in following_headings:
        marker = f"### {next_heading}"
        idx = section.find(marker, start)
        if idx != -1:
            end_candidates.append(idx)

    end = min(end_candidates) if end_candidates else len(section)

    return section[start:end].strip()


def parse_header(text: str) -> dict[str, str | int | float | None]:
    first_heading = re.search(r"^#\s+Core v2 Prompt Suite:\s*(.+?)\s*$", text, flags=re.MULTILINE)

    metadata: dict[str, str | int | float | None] = {
        "suite_name": "core-v2",
        "model_label": first_heading.group(1).strip() if first_heading else None,
        "timestamp_local": None,
        "host": None,
        "model_path": None,
        "llama_cli": None,
        "gpu_layers": None,
        "ctx_size": None,
        "max_tokens": None,
        "temperature": None,
        "system_prompt_path": None,
        "prompt_root": None,
        "include_filter": None,
        "backend": None,
    }

    header_end = text.find("\n## ")
    header = text[:header_end] if header_end != -1 else text

    line_patterns = {
        "timestamp_local": r"^- Date:\s*(.+?)\s*$",
        "host": r"^- Host:\s*(.+?)\s*$",
        "model_path": r"^- Model:\s*`(.+?)`\s*$",
        "llama_cli": r"^- llama-cli:\s*`(.+?)`\s*$",
        "gpu_layers": r"^- GPU layers:\s*(.+?)\s*$",
        "ctx_size": r"^- Context:\s*(.+?)\s*$",
        "max_tokens": r"^- Max generated tokens per prompt:\s*(.+?)\s*$",
        "temperature": r"^- Temperature:\s*(.+?)\s*$",
        "system_prompt_path": r"^- System prompt:\s*`(.+?)`\s*$",
        "prompt_root": r"^- Prompt root:\s*`(.+?)`\s*$",
        "include_filter": r"^- Include filter:\s*`?(.+?)`?\s*$",
    }

    for key, pattern in line_patterns.items():
        match = re.search(pattern, header, flags=re.MULTILINE)
        if not match:
            continue

        value = match.group(1).strip()

        if key in {"gpu_layers", "ctx_size", "max_tokens"}:
            try:
                metadata[key] = int(value)
            except ValueError:
                metadata[key] = None
        elif key == "temperature":
            try:
                metadata[key] = float(value)
            except ValueError:
                metadata[key] = None
        else:
            metadata[key] = value

    build_match = re.search(r"^build\s+:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if build_match:
        metadata["backend"] = f"llama.cpp {build_match.group(1).strip()}"

    return metadata


def split_prompt_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"^##\s+([A-Za-z0-9_-]+)\s*/\s*([A-Za-z0-9_.-]+)\s*$", text, flags=re.MULTILINE))

    sections: list[tuple[str, str, int, int]] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group(0)
        sections.append((title, text[start:end], start, end))

    return [(title, body) for title, body, _, _ in sections]


def parse_prompt_sections(text: str) -> list[PromptSection]:
    parsed: list[PromptSection] = []

    for index, (title, section) in enumerate(split_prompt_sections(text), start=1):
        match = re.match(r"^##\s+([A-Za-z0-9_-]+)\s*/\s*([A-Za-z0-9_.-]+)", title)
        if not match:
            continue

        category = match.group(1).strip()
        prompt_name = match.group(2).strip()

        prompt_file_block = extract_block(section, "Prompt file", ["Prompt", "Output"])
        prompt_file_match = re.search(r"`(.+?)`", prompt_file_block)
        prompt_file = prompt_file_match.group(1).strip() if prompt_file_match else None

        prompt_block = extract_block(section, "Prompt", ["Output"])
        output_block = extract_block(section, "Output", [])

        speed_match = re.search(
            r"\[\s*Prompt:\s*([0-9.]+)\s*t/s\s*\|\s*Generation:\s*([0-9.]+)\s*t/s\s*\]",
            section,
        )

        prompt_eval_tps = float(speed_match.group(1)) if speed_match else None
        generation_tps = float(speed_match.group(2)) if speed_match else None

        parsed.append(
            PromptSection(
                prompt_order=index,
                category=category,
                prompt_name=prompt_name,
                prompt_file=prompt_file,
                prompt_text=strip_code_fence(prompt_block),
                output_text=strip_code_fence(output_block),
                prompt_eval_tps=prompt_eval_tps,
                generation_tps=generation_tps,
            )
        )

    return parsed


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quant_lab_suite_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at_local TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source_report_path TEXT NOT NULL UNIQUE,
            source_report_sha256 TEXT NOT NULL,
            suite_name TEXT,
            model_label TEXT,
            model_path TEXT,
            timestamp_local TEXT,
            host TEXT,
            llama_cli TEXT,
            backend TEXT,
            gpu_layers INTEGER,
            ctx_size INTEGER,
            max_tokens INTEGER,
            temperature REAL,
            system_prompt_path TEXT,
            prompt_root TEXT,
            include_filter TEXT,
            notes TEXT
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quant_lab_prompt_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            suite_run_id INTEGER NOT NULL,
            prompt_order INTEGER NOT NULL,
            category TEXT,
            prompt_name TEXT,
            prompt_file TEXT,
            prompt_text TEXT,
            output_text TEXT,
            prompt_eval_tps REAL,
            generation_tps REAL,
            passed_basic_capture INTEGER,
            notes TEXT,
            FOREIGN KEY(suite_run_id) REFERENCES quant_lab_suite_runs(id),
            UNIQUE(suite_run_id, prompt_order)
        )
        """
    )


def import_report(report_path: Path, notes: str | None = None) -> int:
    resolved = report_path.expanduser().resolve()

    if not resolved.exists():
        raise SystemExit(f"Report not found: {resolved}")

    text = resolved.read_text(encoding="utf-8", errors="replace")
    report_sha256 = sha256_file(resolved)
    metadata = parse_header(text)
    prompts = parse_prompt_sections(text)

    if not prompts:
        raise SystemExit("No prompt sections parsed. No changes written.")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        ensure_schema(conn)

        existing = conn.execute(
            """
            SELECT id FROM quant_lab_suite_runs
            WHERE source_report_path = ?
            """,
            (str(resolved),),
        ).fetchone()

        if existing:
            suite_run_id = int(existing["id"])
            conn.execute(
                """
                UPDATE quant_lab_suite_runs
                SET
                    imported_at_local = CURRENT_TIMESTAMP,
                    source_report_sha256 = ?,
                    suite_name = ?,
                    model_label = ?,
                    model_path = ?,
                    timestamp_local = ?,
                    host = ?,
                    llama_cli = ?,
                    backend = ?,
                    gpu_layers = ?,
                    ctx_size = ?,
                    max_tokens = ?,
                    temperature = ?,
                    system_prompt_path = ?,
                    prompt_root = ?,
                    include_filter = ?,
                    notes = ?
                WHERE id = ?
                """,
                (
                    report_sha256,
                    metadata["suite_name"],
                    metadata["model_label"],
                    metadata["model_path"],
                    metadata["timestamp_local"],
                    metadata["host"],
                    metadata["llama_cli"],
                    metadata["backend"],
                    metadata["gpu_layers"],
                    metadata["ctx_size"],
                    metadata["max_tokens"],
                    metadata["temperature"],
                    metadata["system_prompt_path"],
                    metadata["prompt_root"],
                    metadata["include_filter"],
                    notes,
                    suite_run_id,
                ),
            )
            conn.execute(
                "DELETE FROM quant_lab_prompt_results WHERE suite_run_id = ?",
                (suite_run_id,),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO quant_lab_suite_runs (
                    source_report_path,
                    source_report_sha256,
                    suite_name,
                    model_label,
                    model_path,
                    timestamp_local,
                    host,
                    llama_cli,
                    backend,
                    gpu_layers,
                    ctx_size,
                    max_tokens,
                    temperature,
                    system_prompt_path,
                    prompt_root,
                    include_filter,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(resolved),
                    report_sha256,
                    metadata["suite_name"],
                    metadata["model_label"],
                    metadata["model_path"],
                    metadata["timestamp_local"],
                    metadata["host"],
                    metadata["llama_cli"],
                    metadata["backend"],
                    metadata["gpu_layers"],
                    metadata["ctx_size"],
                    metadata["max_tokens"],
                    metadata["temperature"],
                    metadata["system_prompt_path"],
                    metadata["prompt_root"],
                    metadata["include_filter"],
                    notes,
                ),
            )
            suite_run_id = int(cursor.lastrowid)

        for item in prompts:
            passed_basic_capture = 1 if item.output_text.strip() and item.generation_tps is not None else 0

            conn.execute(
                """
                INSERT INTO quant_lab_prompt_results (
                    suite_run_id,
                    prompt_order,
                    category,
                    prompt_name,
                    prompt_file,
                    prompt_text,
                    output_text,
                    prompt_eval_tps,
                    generation_tps,
                    passed_basic_capture,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    suite_run_id,
                    item.prompt_order,
                    item.category,
                    item.prompt_name,
                    item.prompt_file,
                    item.prompt_text,
                    item.output_text,
                    item.prompt_eval_tps,
                    item.generation_tps,
                    passed_basic_capture,
                    None,
                ),
            )

        conn.commit()

    print(f"Imported suite_run_id={suite_run_id}")
    print(f"Prompt results imported={len(prompts)}")
    print(f"Report SHA256={report_sha256}")

    return suite_run_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import an LLMGauge core-v2 Markdown suite report into Monolith."
    )
    parser.add_argument("report", help="Path to LLMGauge core-v2 Markdown report")
    parser.add_argument("--notes", default=None, help="Optional notes for the suite import")

    args = parser.parse_args()
    import_report(Path(args.report), notes=args.notes)


if __name__ == "__main__":
    main()
