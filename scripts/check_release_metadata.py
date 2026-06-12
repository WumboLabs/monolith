#!/usr/bin/env python3
"""
Validate Monolith release metadata consistency.

This script is read-only. It checks version references and changelog structure
so release notes do not drift or get reordered accidentally.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

VERSION_RE = re.compile(r"^alpha v(\d+(?:\.\d+){1,3})$")
CHANGELOG_HEADING_RE = re.compile(
    r"^## alpha v(\d+(?:\.\d+){1,3}) - \d{4}-\d{2}-\d{2}$"
)


def version_tuple(raw: str) -> tuple[int, int, int, int]:
    match = VERSION_RE.match(raw.strip())
    if not match:
        raise ValueError(f"Invalid version string: {raw!r}")

    parts = [int(part) for part in match.group(1).split(".")]
    while len(parts) < 4:
        parts.append(0)

    return tuple(parts[:4])


def heading_version(raw: str) -> str:
    prefix, _, _date = raw.partition(" - ")
    return prefix.removeprefix("## ").strip()


def read(path: str) -> str:
    return (ROOT / path).read_text()


def main() -> int:
    errors: list[str] = []

    version = read("VERSION").strip()

    if not VERSION_RE.match(version):
        errors.append(f"VERSION is not a valid alpha version: {version!r}")

    app_py = read("dashboard_fastapi/app.py")
    readme = read("README.md")
    public_alpha = read("docs/PUBLIC_ALPHA.md")
    changelog = read("CHANGELOG.md")
    changelog_lines = changelog.splitlines()

    if f'APP_VERSION = "{version}"' not in app_py:
        errors.append("dashboard_fastapi/app.py APP_VERSION does not match VERSION.")

    if f"Current version:\n\n    {version}" not in readme:
        errors.append("README.md current version block does not match VERSION.")

    if f"## Current version\n\n    {version}" not in public_alpha:
        errors.append("docs/PUBLIC_ALPHA.md current version block does not match VERSION.")

    if not changelog_lines:
        errors.append("CHANGELOG.md is empty.")
    elif changelog_lines[0].strip() != "# Monolith Changelog":
        errors.append("CHANGELOG.md must start with '# Monolith Changelog'.")

    title_count = sum(
        1 for line in changelog_lines if line.strip() == "# Monolith Changelog"
    )
    if title_count != 1:
        errors.append(
            f"CHANGELOG.md must contain exactly one '# Monolith Changelog' title; found {title_count}."
        )

    release_headings = [
        line.strip()
        for line in changelog_lines
        if line.startswith("## alpha v")
    ]

    if not release_headings:
        errors.append("CHANGELOG.md has no alpha release headings.")
    else:
        first_release = heading_version(release_headings[0])
        if first_release != version:
            errors.append(
                f"Latest CHANGELOG entry is {first_release!r}, but VERSION is {version!r}."
            )

    parsed_versions: list[tuple[int, int, int, int]] = []
    for heading in release_headings:
        if not CHANGELOG_HEADING_RE.match(heading):
            errors.append(
                "Invalid CHANGELOG release heading. Expected "
                "'## alpha vX.Y[.Z[.N]] - YYYY-MM-DD': "
                f"{heading!r}"
            )
            continue

        try:
            parsed_versions.append(version_tuple(heading_version(heading)))
        except ValueError as exc:
            errors.append(str(exc))

    for previous, current in zip(parsed_versions, parsed_versions[1:]):
        if previous < current:
            errors.append(
                "CHANGELOG release headings are not in descending version order."
            )
            break

    if errors:
        print("Release metadata check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Release metadata OK: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
