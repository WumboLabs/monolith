#!/usr/bin/env python3
"""
Tiny integration test for Monolith model downloader execution.

This does not download a real model. It creates a local temporary source file,
plans a GGUF-like download job pointed at a file:// URL, starts the downloader,
and verifies .part -> final completion behavior.

It is intended for developer validation only.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard_fastapi.app import (
    DB_PATH,
    approved_model_download_root,
    current_timestamp_local,
    get_model_download_job,
    planned_download_destination,
    start_model_download_job,
)


def main() -> None:
    test_repo = "Monolith/Test-Tiny-GGUF"
    test_filename = "monolith-test-tiny-q4_k_m.gguf"
    payload = b"monolith downloader tiny test\n" * 1024

    destination = planned_download_destination(test_repo, test_filename)
    destination_path = Path(destination["destination_path"])
    part_path = destination_path.with_name(destination_path.name + ".part")

    if destination_path.exists():
        destination_path.unlink()

    if part_path.exists():
        part_path.unlink()

    with tempfile.TemporaryDirectory() as tmpdir:
        source_path = Path(tmpdir) / test_filename
        source_path.write_bytes(payload)

        now = current_timestamp_local()

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO model_download_jobs (
                    created_at,
                    updated_at,
                    status,
                    source_type,
                    source_repo_id,
                    source_filename,
                    source_url,
                    destination_root,
                    destination_dir,
                    destination_path,
                    filename,
                    size_bytes,
                    expected_size_bytes,
                    family_guess,
                    quant_guess,
                    architecture_guess,
                    local_match,
                    overwrite_existing,
                    bytes_downloaded,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    now,
                    "planned",
                    "huggingface",
                    test_repo,
                    test_filename,
                    source_path.as_uri(),
                    destination["destination_root"],
                    destination["destination_dir"],
                    destination["destination_path"],
                    test_filename,
                    len(payload),
                    len(payload),
                    "test",
                    "Q4_K_M",
                    "gguf",
                    0,
                    0,
                    0,
                    "Tiny local file:// downloader execution test.",
                ),
            )
            conn.commit()
            job_id = int(cursor.lastrowid)

        try:
            start_model_download_job(job_id)

            deadline = time.time() + 10
            while time.time() < deadline:
                job = get_model_download_job(job_id)
                if job["status"] in {"completed", "failed"}:
                    break
                time.sleep(0.2)

            job = get_model_download_job(job_id)

            print("job_id:", job_id)
            print("status:", job["status"])
            print("bytes_downloaded:", job["bytes_downloaded"])
            print("destination:", destination_path)
            print("approved_root:", approved_model_download_root().expanduser())

            if job["status"] != "completed":
                raise SystemExit(f"Downloader test failed: {job.get('error_text')}")

            if not destination_path.exists():
                raise SystemExit("Downloader test failed: destination file missing.")

            if part_path.exists():
                raise SystemExit("Downloader test failed: .part file still exists after completion.")

            if destination_path.read_bytes() != payload:
                raise SystemExit("Downloader test failed: destination bytes mismatch.")

            print("ok: tiny downloader execution test passed")

        finally:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM model_download_jobs WHERE id = ?", (job_id,))
                conn.commit()

            if destination_path.exists():
                destination_path.unlink()

            if part_path.exists():
                part_path.unlink()


if __name__ == "__main__":
    main()
