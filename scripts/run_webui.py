#!/usr/bin/env python3
"""
Run the Monolith WebUI on the canonical local development port.

Defaults:
  host: 127.0.0.1
  port: 8765

Environment overrides:
  MONOLITH_WEB_HOST
  MONOLITH_WEB_PORT

This launcher is intentionally small and conservative. It checks whether the
configured host/port can be bound before handing off to uvicorn.
"""

from __future__ import annotations

import os
import shlex
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = "8765"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def validate_port(raw_port: str) -> int:
    try:
        port = int(raw_port)
    except ValueError:
        raise SystemExit(f"Invalid MONOLITH_WEB_PORT value: {raw_port!r}")

    if not 1 <= port <= 65535:
        raise SystemExit(f"MONOLITH_WEB_PORT must be between 1 and 65535: {port}")

    return port


def ensure_bind_available(host: str, port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((host, port))
    except OSError as exc:
        raise SystemExit(
            "\n".join(
                [
                    f"Monolith WebUI port is not available: {host}:{port}",
                    f"Reason: {exc}",
                    "",
                    "Check the process using it with:",
                    f"  ss -ltnp 'sport = :{port}'",
                ]
            )
        )


def main() -> int:
    load_dotenv(ENV_PATH)

    host = os.environ.get("MONOLITH_WEB_HOST", DEFAULT_HOST)
    port = validate_port(os.environ.get("MONOLITH_WEB_PORT", DEFAULT_PORT))

    ensure_bind_available(host, port)

    url = f"http://{host}:{port}/"
    print(f"Monolith WebUI: {url}", flush=True)

    argv = [
        sys.executable,
        "-m",
        "uvicorn",
        "dashboard_fastapi.app:app",
        "--host",
        host,
        "--port",
        str(port),
    ]

    print("Command:", " ".join(shlex.quote(part) for part in argv), flush=True)
    os.execv(sys.executable, argv)


if __name__ == "__main__":
    raise SystemExit(main())
