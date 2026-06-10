#!/usr/bin/env python3

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

for path in DATA.glob("llm-tests.sqlite*"):
    print(f"Removing {path}")
    path.unlink()

print("Reinitializing database...")
init_script = ROOT / "scripts" / "init_db.py"

import subprocess
subprocess.run([str(init_script)], check=True)

print("Database reset complete.")
