# WumboJetsII Local LLM Testbench

Timestamped local model, quant, and inference-configuration testing framework for WumboJetsII.

## Goals

- Compare local models against the current daily-driver baseline.
- Track quant quality and performance.
- Preserve prompt/response history.
- Record llama.cpp build, launcher, context, cache, and performance settings.
- Build toward a local dashboard without disturbing production launchers.

## Current baseline

Production launcher:

    lmoeai

Experimental long-context launcher:

    lmoeai-tq

Current champion:

    Qwen3.6-35B-A3B-UD-IQ2_M

## Rules

- Do not modify production llama.cpp from this project.
- Do not modify existing launchers unless explicitly planned.
- Treat TurboQuant as experimental.
- Compare all candidates against Qwen3.6-35B-A3B.
- Prefer repeatable tests over one-off impressions.
- Timestamp all runs and notes.

## Versioning

Monolith uses milestone + patch versioning during alpha development.

Examples:

- alpha v0.10.0 — known-good feature/milestone baseline
- alpha v0.10.0.3.2 — small UI/UX polish, bugfix, or cleanup after v0.02
- alpha v0.10.0.3.2 — next small patch
- alpha v0.10.0.3.2 — next feature milestone

Patch numbers do not stop at .9; use .10, .11, etc. if needed.

Current version is tracked in:

- VERSION
- dashboard_fastapi/app.py as APP_VERSION
- CHANGELOG.md

Current active version:

    alpha v0.10.0.3.2
