# Monolith

**Local AI Workbench for testing, comparing, and evaluating local LLMs on real hardware.**

Monolith is a local-first dashboard and evaluation workbench for practical local AI testing. It is built around real workstation constraints: model profiles, GGUF paths, llama.cpp launchers, context scaling, prompt suites, generation speed, VRAM behavior, and repeatable model comparisons.

> Real hardware. Real testing. No hype.

## Project status

Monolith is alpha software.

It is currently useful as a local AI workbench for technical users, but it is not yet packaged as a general-purpose application. Expect rough edges, manual setup, and active iteration.

Current version:

    alpha v0.11.10

## What Monolith is for

Monolith is intended to help answer practical local AI questions:

- Which local model is actually useful on this hardware?
- How does a model behave across context sizes?
- How fast does it run with a given quant, launcher, and cache setup?
- Does it follow operational safety constraints?
- Does it hallucinate under uncertainty?
- Can it handle Linux, Docker, ZFS, config review, and coding prompts reliably?
- Which model should be used for daily work, long-context work, or agent backend experiments?

## Current capabilities

Monolith currently includes:

- Local model profile tracking
- Chat/test run logging
- Prompt and response metadata capture
- Token count and speed tracking
- VRAM/performance fields
- Core local-eval prompt suites
- Context-scaling evaluation scaffolding
- Agent Lab planning/review scaffolding
- Agent backend evaluation prompt suites
- FastAPI-based local dashboard UI

## Current safety posture

Monolith is designed to run locally on a trusted machine.

The repository intentionally excludes:

- `.env` files
- API keys and tokens
- passwords
- private SSH keys
- SQLite databases
- raw logs
- local model binaries
- screenshots with private data
- real local model configuration files

Use the sanitized examples under `configs/` as templates for local configuration.

See [`docs/PUBLIC_ALPHA.md`](docs/PUBLIC_ALPHA.md) for current public-alpha status, limitations, and expected setup path.

## Local configuration

Real local configuration files are ignored by Git.

Use:

    configs/models.example.yaml

as starting points, then copy them locally to:

    configs/models.yaml

Do not commit your real local config files.

## Development rules

This project follows a conservative local-first workflow:

- Prefer small, reversible changes.
- Keep generated data out of Git.
- Keep real model paths, private machine details, and local benchmark data out of public files.
- Run scans before public-facing commits.
- Do not add automatic command execution without review boundaries.
- Treat agent workflows as proposal/review-first until proven safe.
- Keep llama.cpp and production launchers outside this repo unless explicitly planned.

## Versioning

Monolith uses alpha milestone versioning.

Recent examples:

- `alpha v0.11.5` — WumboCore / Monochrome Lime theme pass and Agent Lab archiving
- `alpha v0.11.6` — portable Workstation monitoring and ticker hardening
- `alpha v0.11.7` — public-alpha generic install audit and documentation cleanup
- `alpha v0.11.10` — clean-clone install validation, public-alpha doc hardening, LLMGauge terminology cleanup, and runtime/dependency roadmap planning
- `alpha v0.11.9` — terminal workbench UI shell, fixed local WebUI launcher, table pagination, active tabs, and typography refinement
- `alpha v0.11.8` — first-run setup diagnostics and setup hardening

Next planned milestone:

- `alpha v0.11.11` — setup doctor hardening and clearer dependency/runtime diagnostics

## Canonical local WebUI

Monolith's local development WebUI uses one fixed default address:

    http://127.0.0.1:8765/

Start it with:

    python scripts/run_webui.py

The default can be overridden through `MONOLITH_WEB_HOST` and `MONOLITH_WEB_PORT`, but project docs and local validation should use port `8765`.

Current version is tracked in:

- `VERSION`
- `dashboard_fastapi/app.py` as `APP_VERSION`
- `CHANGELOG.md`

Before committing release metadata changes, run:

    python scripts/check_release_metadata.py

This checks that version references match, the changelog title stays at the top, and the latest changelog entry matches `VERSION`.

## Security

See [`SECURITY.md`](SECURITY.md).

## License

No open-source license has been selected yet.

Until a license is added, this repository is public for visibility and review, but reuse rights are not granted beyond GitHub's normal viewing/forking terms.
