# Monolith

**Local AI Workbench for testing, comparing, and evaluating local LLMs on real hardware.**

Monolith is a local-first dashboard and evaluation workbench for practical local AI testing. It is built around real workstation constraints: model profiles, GGUF paths, llama.cpp launchers, context scaling, prompt suites, generation speed, VRAM behavior, and repeatable model comparisons.

> Real hardware. Real testing. No hype.

## Project status

Monolith is alpha software.

It is currently useful as a personal/local AI workbench, but it is not yet packaged as a general-purpose application. Expect workstation-specific assumptions, rough edges, and active iteration.

Current version:

    alpha v0.11.5

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

Use the sanitized examples under `examples/config/` as templates for local configuration.

## Local configuration

Real local configuration files are ignored by Git.

Use:

    examples/config/models.example.yaml
    examples/config/test_profiles.example.yaml

as starting points, then copy them locally to:

    configs/models.yaml
    configs/test_profiles.yaml

Do not commit your real local config files.

## Development rules

This project follows a conservative local-first workflow:

- Prefer small, reversible changes.
- Keep generated data out of Git.
- Keep real model paths and private machine details out of public files.
- Run scans before public-facing commits.
- Do not add automatic command execution without review boundaries.
- Treat agent workflows as proposal/review-first until proven safe.
- Keep llama.cpp and production launchers outside this repo unless explicitly planned.

## Versioning

Monolith uses alpha milestone versioning.

Examples:

- `alpha v0.10.0` — initial public preflight baseline
- `alpha v0.11.4` — public-alpha readiness, generated chat profiles, model detail pages, local prompt scaffold, and install docs
- `alpha v0.11.3` — controlled downloader execution and UI
- `alpha v0.11.6` — next feature milestone
- `alpha v0.11.6.1` — small patch after that milestone

Current version is tracked in:

- `VERSION`
- `dashboard_fastapi/app.py` as `APP_VERSION`
- `CHANGELOG.md`

## Security

See [`SECURITY.md`](SECURITY.md).

## License

No open-source license has been selected yet.

Until a license is added, this repository is public for visibility and review, but reuse rights are not granted beyond GitHub's normal viewing/forking terms.
