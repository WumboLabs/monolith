#!/usr/bin/env python3
"""
Print Monolith first-run setup diagnostics.

This script is read-only. It does not create files, run migrations, download
models, start model processes, or modify configuration.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def status_rank(status: str) -> int:
    if status == "error":
        return 0
    if status == "warn":
        return 1
    return 2


def status_marker(status: str) -> str:
    if status == "ok":
        return "[OK]"
    if status == "warn":
        return "[WARN]"
    if status == "error":
        return "[ERROR]"
    return "[UNKNOWN]"


def print_text_report(payload: dict[str, Any]) -> None:
    print(f"Monolith setup status: {payload['overall_status'].upper()}")
    print(payload["summary"])
    print()

    counts = payload["counts"]
    print(
        "Checks: "
        f"{counts['total']} total, "
        f"{counts['ok']} ok, "
        f"{counts['warn']} warn, "
        f"{counts['error']} error"
    )
    print()

    checks = sorted(
        payload["checks"],
        key=lambda item: (status_rank(item["status"]), item["label"].lower()),
    )

    for check in checks:
        print(f"{status_marker(check['status'])} {check['label']}")
        print(f"  Detail: {check['detail']}")
        print(f"  Next:   {check['next_action']}")
        print()

    print("Paths:")
    for key, value in payload["paths"].items():
        print(f"  {key}: {value}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run read-only Monolith setup diagnostics."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of a text report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return a non-zero process status when errors are present.",
    )
    return parser.parse_args()


def dependency_error_payload(exc: ModuleNotFoundError) -> dict[str, Any]:
    missing = exc.name or "unknown"

    return {
        "overall_status": "error",
        "summary": (
            "Setup diagnostics could not load Monolith's Python application "
            "dependencies."
        ),
        "counts": {
            "total": 1,
            "ok": 0,
            "warn": 0,
            "error": 1,
        },
        "checks": [
            {
                "status": "error",
                "label": "Python dependencies",
                "detail": f"Missing Python module: {missing}",
                "next_action": (
                    "Activate the Monolith virtual environment and install "
                    "requirements: source .venv/bin/activate && "
                    "python -m pip install -r requirements.txt"
                ),
            }
        ],
        "paths": {
            "root": str(ROOT),
            "python": sys.executable,
        },
    }


def main() -> int:
    args = parse_args()

    try:
        from dashboard_fastapi.app import setup_status_payload
    except ModuleNotFoundError as exc:
        payload = dependency_error_payload(exc)
    else:
        payload = setup_status_payload()

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print_text_report(payload)

    if args.strict and payload["counts"]["error"] > 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
