#!/usr/bin/env python3
"""Repo-local bootstrap helper for Monolith.

This script prepares a cloned Monolith checkout without mutating system-level
dependencies. It is intentionally conservative:
- no sudo
- no system package manager calls
- no GPU driver/CUDA changes
- no llama.cpp builds
- no model downloads
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"
REQUIREMENTS = ROOT / "requirements.txt"

RUNTIME_DIRS = [
    ROOT / "data",
    ROOT / "tmp",
    ROOT / "logs",
    ROOT / "cache",
]

MIGRATION_SCRIPTS = [
    ROOT / "scripts" / "init_db.py",
    ROOT / "scripts" / "migrate_model_registry.py",
    ROOT / "scripts" / "migrate_model_downloader.py",
    ROOT / "scripts" / "migrate_generated_chat_profiles.py",
    ROOT / "scripts" / "migrate_context_scaling.py",
    ROOT / "scripts" / "migrate_hermes_eval.py",
    ROOT / "scripts" / "migrate_agent_lab.py",
]


def print_step(message: str) -> None:
    print(f"== {message} ==")


def run(cmd: list[str], *, dry_run: bool, cwd: Path = ROOT) -> None:
    print("+ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_runtime_dirs(*, dry_run: bool) -> None:
    print_step("runtime directories")
    for path in RUNTIME_DIRS:
        if path.exists():
            print(f"ok: {path.relative_to(ROOT)}")
            continue
        print(f"create: {path.relative_to(ROOT)}")
        if not dry_run:
            path.mkdir(parents=True, exist_ok=True)


def ensure_models_config(*, dry_run: bool, force_config: bool, yes: bool) -> None:
    print_step("models config")
    src = ROOT / "configs" / "models.example.yaml"
    dst = ROOT / "configs" / "models.yaml"

    if not src.exists():
        raise SystemExit(f"missing example config: {src}")

    if dst.exists() and not force_config:
        print(f"ok: {dst.relative_to(ROOT)} already exists")
        return

    if dst.exists() and force_config:
        if not yes and not dry_run:
            raise SystemExit(
                "--force-config would overwrite configs/models.yaml. "
                "Re-run with --force-config --yes to confirm."
            )
        print(f"overwrite: {dst.relative_to(ROOT)} from {src.relative_to(ROOT)}")
    else:
        print(f"copy: {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")

    if not dry_run:
        shutil.copyfile(src, dst)


def ensure_venv(*, dry_run: bool, python_executable: str) -> None:
    print_step("virtual environment")
    if VENV_PYTHON.exists():
        print(f"ok: {VENV_PYTHON.relative_to(ROOT)}")
        return

    run([python_executable, "-m", "venv", str(VENV_DIR)], dry_run=dry_run)


def install_requirements(*, dry_run: bool, skip_pip: bool) -> None:
    print_step("python requirements")
    if skip_pip:
        print("skip: --skip-pip")
        return

    if not REQUIREMENTS.exists():
        raise SystemExit(f"missing requirements file: {REQUIREMENTS}")

    if not dry_run and not VENV_PYTHON.exists():
        raise SystemExit(f"missing venv python: {VENV_PYTHON}")

    python_cmd = str(VENV_PYTHON) if VENV_PYTHON.exists() else str(VENV_PYTHON)
    run([python_cmd, "-m", "pip", "install", "-r", str(REQUIREMENTS)], dry_run=dry_run)


def run_migrations(*, dry_run: bool, skip_db: bool) -> None:
    print_step("database initialization and migrations")
    if skip_db:
        print("skip: --skip-db")
        return

    for script in MIGRATION_SCRIPTS:
        if not script.exists():
            raise SystemExit(f"missing migration script: {script}")
        run([str(VENV_PYTHON), str(script)], dry_run=dry_run)


def run_setup_check(*, dry_run: bool, skip_setup_check: bool) -> None:
    print_step("setup check")
    if skip_setup_check:
        print("skip: --skip-setup-check")
        return

    script = ROOT / "scripts" / "setup_check.py"
    if not script.exists():
        raise SystemExit(f"missing setup check script: {script}")

    run([str(VENV_PYTHON), str(script)], dry_run=dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare a cloned Monolith repo using repo-local setup steps only."
    )
    parser.add_argument("--dry-run", action="store_true", help="Print actions without changing files.")
    parser.add_argument("--skip-pip", action="store_true", help="Do not install requirements.txt.")
    parser.add_argument("--skip-db", action="store_true", help="Do not run DB initialization/migrations.")
    parser.add_argument("--skip-setup-check", action="store_true", help="Do not run scripts/setup_check.py at the end.")
    parser.add_argument("--force-config", action="store_true", help="Overwrite configs/models.yaml from the example config.")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive bootstrap actions such as --force-config.")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to create .venv when it does not exist.",
    )

    args = parser.parse_args()

    print("Monolith repo-local bootstrap")
    print(f"root: {ROOT}")
    print(f"dry_run: {args.dry_run}")
    print()

    ensure_venv(dry_run=args.dry_run, python_executable=args.python)
    install_requirements(dry_run=args.dry_run, skip_pip=args.skip_pip)
    ensure_runtime_dirs(dry_run=args.dry_run)
    ensure_models_config(dry_run=args.dry_run, force_config=args.force_config, yes=args.yes)
    run_migrations(dry_run=args.dry_run, skip_db=args.skip_db)
    run_setup_check(dry_run=args.dry_run, skip_setup_check=args.skip_setup_check)

    print()
    print("Bootstrap complete.")
    print("Next: source .venv/bin/activate")
    print("Next: set MONOLITH_LLAMA_COMPLETION / MONOLITH_LLAMA_TOKENIZE in .env if llama.cpp lives outside the repo")
    print("Next: python scripts/run_webui.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
