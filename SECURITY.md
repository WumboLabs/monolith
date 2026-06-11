# Security Policy

Monolith is an alpha-stage local AI workbench for experimenting with local LLMs, evaluation prompts, model profiles, and workstation-oriented workflows.

## Current security posture

Monolith is intended to run locally on a trusted machine.

The repository should not contain:

- API keys
- tokens
- passwords
- private SSH keys
- `.env` files
- real local model configuration files
- SQLite databases
- raw logs
- model binaries
- screenshots with private data

Real local configuration files such as `configs/models.yaml` and `configs/test_profiles.yaml` are intentionally ignored by Git.

Use the sanitized examples under `configs/`, such as `configs/models.example.yaml`, as templates.

## Agent and command-execution caution

Monolith includes early Agent Lab and evaluation scaffolding.

At this stage:

- agent workflows should remain bounded and review-first
- command execution should not be automatic
- file mutation should require explicit review
- arbitrary workspace paths should not be trusted
- Docker socket mounts, SSH key mounts, and broad host mounts should be treated as high-risk

## Reporting issues

For now, report security concerns privately to the repository owner.

Do not open a public issue containing secrets, tokens, local paths, screenshots, or sensitive logs.
