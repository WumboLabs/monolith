#!/usr/bin/env python3
"""
Import LLMGauge result artifacts into Monolith.

Supported inputs:
- single run directory containing llmgauge-result.json
- ladder directory containing ladder-summary.json
- export index JSON with schema_version = llmgauge.export_index.v0

This importer is intentionally additive. It writes only to llmgauge_* tables
and does not modify Quant Lab, context scaling, Hermes Eval, or Agent Lab data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "llm-tests.sqlite"

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


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError_COMPAT as exc:
        raise SystemExit(f"Invalid JSON: {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise SystemExit(f"Expected JSON object: {path}")

    return data


# Compatibility alias keeps type checkers quiet while preserving a single import block.
JSONDecodeError_COMPAT = json.JSONDecodeError


def sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_from_metadata(summary: ArtifactSummary, key: str) -> Path | None:
    value = summary.metadata.get(key)
    if not value:
        return None
    return Path(str(value)).expanduser()


def source_hash_for_summary(summary: ArtifactSummary) -> str | None:
    if summary.artifact_type == "run":
        return sha256_file(path_from_metadata(summary, "result_json"))
    if summary.artifact_type == "ladder":
        return sha256_file(path_from_metadata(summary, "ladder_summary"))
    return None


def detect_input(path: Path) -> str:
    if path.is_file():
        data = load_json(path)
        if data.get("schema_version") == EXPORT_INDEX_SCHEMA:
            return "index"
        raise SystemExit(
            "Unsupported JSON file. Expected schema_version "
            f"{EXPORT_INDEX_SCHEMA!r}: {path}"
        )

    if path.is_dir() and (path / "llmgauge-result.json").exists():
        return "run"

    if path.is_dir() and (path / "ladder-summary.json").exists():
        return "ladder"

    raise SystemExit(
        "Unsupported input. Expected run dir, ladder dir, or LLMGauge export index JSON: "
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

    run = data.get("run") if isinstance(data.get("run"), dict) else {}
    suite = data.get("suite") if isinstance(data.get("suite"), dict) else {}
    model = data.get("model") if isinstance(data.get("model"), dict) else {}
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}

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
            "run_id": run.get("run_id"),
            "status": run.get("status"),
            "timestamp_utc": run.get("timestamp_utc"),
            "suite_id": suite.get("suite_id"),
            "suite_version": suite.get("suite_version"),
            "model_id": model.get("model_id"),
            "model_profile": model.get("model_profile"),
            "prompt_count": suite.get("prompt_count"),
            "completed": summary.get("completed"),
            "failed": summary.get("failed"),
            "manual_score_total": summary.get("manual_score_total"),
            "manual_score_max": summary.get("manual_score_max"),
            "has_raw_artifacts": (path / "raw").exists(),
            "has_logs": (path / "logs").exists(),
        },
    )


def summarize_ladder_dir(path: Path) -> ArtifactSummary:
    ladder_summary = path / "ladder-summary.json"
    data = load_json(ladder_summary)

    schema_version = data.get("schema_version")
    validation_status = "valid" if schema_version == LADDER_SCHEMA else "unknown"

    child_runs = sorted(
        child for child in path.iterdir() if child.is_dir() and child.name.startswith("ctx-")
    )
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}

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
            "completed": summary.get("completed"),
            "failed": summary.get("failed"),
            "total": summary.get("total"),
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


def ensure_tables(conn: sqlite3.Connection) -> None:
    required = {
        "llmgauge_artifact_imports",
        "llmgauge_run_summaries",
        "llmgauge_ladder_summaries",
    }
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'llmgauge_%'"
    ).fetchall()
    existing = {str(row[0]) for row in rows}
    missing = sorted(required - existing)
    if missing:
        raise SystemExit(
            "Missing LLMGauge import tables. Run scripts/migrate_llmgauge_imports.py first. "
            f"Missing: {', '.join(missing)}"
        )


def upsert_artifact_import(conn: sqlite3.Connection, summary: ArtifactSummary) -> int:
    metadata = summary.metadata
    source_hash = source_hash_for_summary(summary)

    result_json_path = optional_text(metadata.get("result_json"))
    report_path = optional_text(metadata.get("report"))
    ladder_summary_path = optional_text(metadata.get("ladder_summary"))
    ladder_report_path = optional_text(metadata.get("ladder_report"))

    raw_dir_path = None
    logs_dir_path = None
    if summary.artifact_type == "run":
        raw_candidate = summary.source_path / "raw"
        logs_candidate = summary.source_path / "logs"
        raw_dir_path = str(raw_candidate) if raw_candidate.exists() else None
        logs_dir_path = str(logs_candidate) if logs_candidate.exists() else None

    existing = conn.execute(
        """
        SELECT id
        FROM llmgauge_artifact_imports
        WHERE source_path = ? AND artifact_type = ?
        """,
        (str(summary.source_path), summary.artifact_type),
    ).fetchone()

    values = (
        summary.artifact_type,
        str(summary.source_path),
        summary.source_path_kind,
        source_hash,
        summary.schema_version,
        utc_now_iso(),
        bool_int(summary.validation_checked),
        summary.validation_status,
        json_dumps(summary.validation_errors),
        json_dumps(metadata),
        result_json_path,
        report_path,
        ladder_summary_path,
        ladder_report_path,
        raw_dir_path,
        logs_dir_path,
    )

    if existing:
        import_id = int(existing[0])
        conn.execute(
            """
            UPDATE llmgauge_artifact_imports
            SET artifact_type = ?,
                source_path = ?,
                source_path_kind = ?,
                source_hash = ?,
                schema_version = ?,
                imported_at_utc = ?,
                validation_checked = ?,
                validation_status = ?,
                validation_errors_json = ?,
                artifact_json = ?,
                result_json_path = ?,
                report_path = ?,
                ladder_summary_path = ?,
                ladder_report_path = ?,
                raw_dir_path = ?,
                logs_dir_path = ?
            WHERE id = ?
            """,
            (*values, import_id),
        )
        conn.execute("DELETE FROM llmgauge_run_summaries WHERE import_id = ?", (import_id,))
        conn.execute("DELETE FROM llmgauge_ladder_summaries WHERE import_id = ?", (import_id,))
        return import_id

    cursor = conn.execute(
        """
        INSERT INTO llmgauge_artifact_imports (
            artifact_type,
            source_path,
            source_path_kind,
            source_hash,
            schema_version,
            imported_at_utc,
            validation_checked,
            validation_status,
            validation_errors_json,
            artifact_json,
            result_json_path,
            report_path,
            ladder_summary_path,
            ladder_report_path,
            raw_dir_path,
            logs_dir_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    return int(cursor.lastrowid)


def insert_run_summary(conn: sqlite3.Connection, import_id: int, metadata: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO llmgauge_run_summaries (
            import_id,
            run_id,
            status,
            timestamp_utc,
            suite_id,
            suite_version,
            model_id,
            model_profile_json,
            prompt_count,
            completed,
            failed,
            manual_score_total,
            manual_score_max,
            has_raw_artifacts,
            has_logs
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            import_id,
            optional_text(metadata.get("run_id")),
            optional_text(metadata.get("status")),
            optional_text(metadata.get("timestamp_utc")),
            optional_text(metadata.get("suite_id")),
            optional_text(metadata.get("suite_version")),
            optional_text(metadata.get("model_id")),
            json_dumps(metadata.get("model_profile") or {}),
            optional_int(metadata.get("prompt_count")),
            optional_int(metadata.get("completed")),
            optional_int(metadata.get("failed")),
            optional_float(metadata.get("manual_score_total")),
            optional_float(metadata.get("manual_score_max")),
            bool_int(metadata.get("has_raw_artifacts")),
            bool_int(metadata.get("has_logs")),
        ),
    )


def insert_ladder_summary(conn: sqlite3.Connection, import_id: int, metadata: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO llmgauge_ladder_summaries (
            import_id,
            ladder_id,
            suite_id,
            model_id,
            include_json,
            only_json,
            contexts_json,
            child_run_count,
            completed,
            failed,
            total,
            has_child_runs
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            import_id,
            optional_text(metadata.get("ladder_id")),
            optional_text(metadata.get("suite_id")),
            optional_text(metadata.get("model_id")),
            json_dumps(metadata.get("include") or []),
            json_dumps(metadata.get("only") or []),
            json_dumps(metadata.get("contexts") or []),
            optional_int(metadata.get("child_run_count")),
            optional_int(metadata.get("completed")),
            optional_int(metadata.get("failed")),
            optional_int(metadata.get("total")),
            bool_int(metadata.get("has_child_runs")),
        ),
    )


def import_summary(conn: sqlite3.Connection, summary: ArtifactSummary) -> int:
    import_id = upsert_artifact_import(conn, summary)

    if summary.artifact_type == "run":
        insert_run_summary(conn, import_id, summary.metadata)
    elif summary.artifact_type == "ladder":
        insert_ladder_summary(conn, import_id, summary.metadata)
    else:
        raise SystemExit(f"Unsupported artifact type: {summary.artifact_type}")

    return import_id


def import_summaries(summaries: list[ArtifactSummary], db_path: Path) -> list[int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        ensure_tables(conn)

        import_ids = [import_summary(conn, summary) for summary in summaries]

        conn.commit()
        return import_ids


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
    parser.add_argument("path", type=Path, help="Run dir, ladder dir, or LLMGauge export index JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detect and summarize artifacts without writing to the database.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help=f"Monolith SQLite database path. Default: {DB_PATH}",
    )

    args = parser.parse_args()
    path = args.path.expanduser().resolve()
    db_path = args.db.expanduser().resolve()

    summaries = summarize_input(path)

    if args.dry_run:
        print(f"detected_artifacts: {len(summaries)}")
        for index, summary in enumerate(summaries, start=1):
            print()
            print(f"== artifact {index} ==")
            print_summary(summary)
        return

    import_ids = import_summaries(summaries, db_path)

    print(f"imported_artifacts: {len(import_ids)}")
    for import_id, summary in zip(import_ids, summaries, strict=True):
        print(
            f"import_id={import_id} "
            f"artifact_type={summary.artifact_type} "
            f"validation_status={summary.validation_status} "
            f"source_path={summary.source_path}"
        )


if __name__ == "__main__":
    main()
