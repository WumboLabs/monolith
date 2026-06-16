#!/usr/bin/env python3
"""
Import LLMGauge result artifacts into Monolith.

Initial version: detect and summarize supported LLMGauge v0.13 artifacts.
DB writes will be added after detection is verified against real artifacts.

Supported inputs:
- single run directory containing llmgauge-result.json
- ladder directory containing ladder-summary.json
- export index file named llmgauge-index.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RUN_SCHEMA = "llmgauge.result.v0"
LADDER_SCHEMA = "llmgauge.context_ladder.v0"
EXPORT_INDEX_SCHEMA = "llmgauge.export_index.v0"


@dataclass(frozen=True)
class ArtifactSummary:
    artifact_type: str
    source_path: Path
    source_path_kind: str
    schema_version: str | None
    validation_checked: bool
    validation_status: str
    validation_errors: list[str]
    metadata: dict[str, Any]


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object: {path}")

    return data


def detect_input(path: Path) -> str:
    if path.is_file() and path.name == "llmgauge-index.json":
        return "index"

    if path.is_dir() and (path / "llmgauge-result.json").exists():
        return "run"

    if path.is_dir() and (path / "ladder-summary.json").exists():
        return "ladder"

    raise SystemExit(
        "Unsupported input. Expected run dir, ladder dir, or llmgauge-index.json: "
        f"{path}"
    )


def validation_from_item(item: dict[str, Any]) -> tuple[bool, str, list[str]]:
    validation = item.get("validation")
    if not isinstance(validation, dict):
        return False, "unknown", []

    checked = bool(validation.get("checked", False))
    status = str(validation.get("status") or "unknown")
    errors_raw = validation.get("errors", [])

    errors: list[str] = []
    if isinstance(errors_raw, list):
        errors = [str(item) for item in errors_raw]

    if status not in {"valid", "invalid", "unknown"}:
        status = "unknown"

    return checked, status, errors


def summarize_run_dir(path: Path) -> ArtifactSummary:
    result_json = path / "llmgauge-result.json"
    data = load_json(result_json)

    schema_version = data.get("schema_version")
    validation_status = "valid" if schema_version == RUN_SCHEMA else "unknown"

    return ArtifactSummary(
        artifact_type="run",
        source_path=path.resolve(),
        source_path_kind="directory",
        schema_version=str(schema_version) if schema_version else None,
        validation_checked=False,
        validation_status=validation_status,
        validation_errors=[],
        metadata={
            "result_json": str(result_json),
            "report": str(path / "report.md") if (path / "report.md").exists() else None,
            "run_id": data.get("run_id"),
            "status": data.get("status"),
            "timestamp_utc": data.get("timestamp_utc"),
            "suite_id": data.get("suite_id"),
            "suite_version": data.get("suite_version"),
            "model_id": data.get("model_id"),
            "model_profile": data.get("model_profile"),
            "prompt_count": data.get("prompt_count"),
            "completed": data.get("completed"),
            "failed": data.get("failed"),
            "manual_score_total": data.get("manual_score_total"),
            "manual_score_max": data.get("manual_score_max"),
            "has_raw_artifacts": (path / "raw").exists(),
            "has_logs": (path / "logs").exists(),
        },
    )


def summarize_ladder_dir(path: Path) -> ArtifactSummary:
    ladder_summary = path / "ladder-summary.json"
    data = load_json(ladder_summary)

    schema_version = data.get("schema_version")
    validation_status = "valid" if schema_version == LADDER_SCHEMA else "unknown"

    child_runs = sorted(child for child in path.iterdir() if child.is_dir() and child.name.startswith("ctx-"))

    return ArtifactSummary(
        artifact_type="ladder",
        source_path=path.resolve(),
        source_path_kind="directory",
        schema_version=str(schema_version) if schema_version else None,
        validation_checked=False,
        validation_status=validation_status,
        validation_errors=[],
        metadata={
            "ladder_summary": str(ladder_summary),
            "ladder_report": str(path / "ladder-report.md")
            if (path / "ladder-report.md").exists()
            else None,
            "ladder_id": data.get("ladder_id"),
            "suite_id": data.get("suite_id"),
            "model_id": data.get("model_id"),
            "include": data.get("include"),
            "only": data.get("only"),
            "contexts": data.get("contexts"),
            "child_run_count": data.get("child_run_count", len(child_runs)),
            "completed": data.get("completed"),
            "failed": data.get("failed"),
            "total": data.get("total"),
            "has_child_runs": bool(child_runs),
        },
    )


def summarize_index(path: Path) -> list[ArtifactSummary]:
    data = load_json(path)

    schema_version = data.get("schema_version")
    if schema_version != EXPORT_INDEX_SCHEMA:
        raise SystemExit(
            f"Unsupported export index schema: {schema_version!r}; expected {EXPORT_INDEX_SCHEMA}"
        )

    items = data.get("items", [])
    if not isinstance(items, list):
        raise SystemExit(f"Invalid export index items list: {path}")

    summaries: list[ArtifactSummary] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        artifact_type = str(item.get("artifact_type") or "")
        if artifact_type not in {"run", "ladder"}:
            continue

        checked, status, errors = validation_from_item(item)

        summaries.append(
            ArtifactSummary(
                artifact_type=artifact_type,
                source_path=Path(str(item.get("path") or "")).expanduser(),
                source_path_kind="index_item",
                schema_version=str(item.get("schema_version") or ""),
                validation_checked=checked,
                validation_status=status,
                validation_errors=errors,
                metadata=item,
            )
        )

    return summaries


def summarize_input(path: Path) -> list[ArtifactSummary]:
    kind = detect_input(path)

    if kind == "run":
        return [summarize_run_dir(path)]

    if kind == "ladder":
        return [summarize_ladder_dir(path)]

    return summarize_index(path)


def print_summary(summary: ArtifactSummary) -> None:
    print(f"artifact_type: {summary.artifact_type}")
    print(f"source_path: {summary.source_path}")
    print(f"source_path_kind: {summary.source_path_kind}")
    print(f"schema_version: {summary.schema_version}")
    print(f"validation_checked: {summary.validation_checked}")
    print(f"validation_status: {summary.validation_status}")
    print(f"validation_errors: {json.dumps(summary.validation_errors)}")
    print("metadata:")
    print(json.dumps(summary.metadata, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import LLMGauge artifacts into Monolith.")
    parser.add_argument("path", type=Path, help="Run dir, ladder dir, or llmgauge-index.json")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and summarize artifacts without writing to the database.",
    )

    args = parser.parse_args()
    path = args.path.expanduser().resolve()

    summaries = summarize_input(path)

    if not args.dry_run:
        raise SystemExit("DB import is not implemented yet. Re-run with --dry-run.")

    print(f"detected_artifacts: {len(summaries)}")
    for index, summary in enumerate(summaries, start=1):
        print()
        print(f"== artifact {index} ==")
        print_summary(summary)


if __name__ == "__main__":
    main()
