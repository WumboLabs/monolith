# Public Alpha Status

Monolith is currently a technical public alpha for Linux users who are comfortable with local model runtimes, GGUF files, Python virtual environments, and llama.cpp.

It is not yet packaged as a general-purpose desktop app or one-command installer.

## Current version

    alpha v0.11.12

## Intended users

Monolith is currently intended for users who:

- run local GGUF models
- have or can build llama.cpp
- are comfortable editing YAML config files
- understand that local model paths vary by machine
- can troubleshoot Python virtual environments and command-line tools

## Current supported install path

The supported alpha path is:

    git clone https://github.com/WumboLabs/monolith.git
    cd monolith
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    cp configs/models.example.yaml configs/models.yaml
    python scripts/init_db.py
    python scripts/migrate_model_registry.py
    python scripts/migrate_model_downloader.py
    python scripts/migrate_generated_chat_profiles.py
    python scripts/migrate_context_scaling.py
    python scripts/migrate_hermes_eval.py
    python scripts/migrate_agent_lab.py
    python scripts/setup_check.py
    python scripts/run_webui.py

See `docs/INSTALL.md` for the full sequence.

## What works

- Local FastAPI web UI
- First-run setup diagnostics through `/setup`, `/api/setup/status`, and `scripts/setup_check.py`
- Local GGUF model registry
- Generated chat profiles from discovered local models
- Controlled Hugging Face GGUF download planning and execution
- Basic chat against configured llama.cpp profiles
- Local Eval / prompt-suite browsing and imports
- Context-scaling and agent-backend evaluation scaffolding
- Agent Lab proposal/review/read-only workflow scaffolding
- Workstation monitoring with CPU, memory, root disk, and optional NVIDIA GPU stats
- Graceful monitoring fallback when `nvidia-smi` or other machine-specific metrics are unavailable

## What does not work yet

- No bundled llama.cpp installation
- No GPU driver, CUDA, ROCm, or runtime setup
- No one-command install
- No Docker-first public install path
- No full model-profile editor
- No general plugin system
- No authenticated multi-user deployment model
- No production security hardening for public network exposure

## Privacy and local files

Do not commit:

- `.env`
- `configs/models.yaml`
- SQLite databases
- model files
- local run logs
- benchmark outputs
- screenshots containing private data
- private prompts

Use:

    configs/models.example.yaml
    .env.example
    prompts/local/

for safe examples and local/private prompt separation.

## Public-alpha expectations

Expect rough edges, manual setup, and active iteration.

After running migrations, use:

    python scripts/setup_check.py

or open:

    /setup

to review read-only first-run diagnostics.

A clean install should not require the original author's machine names, model paths, homelab paths, or private infrastructure.

## Release date note

Use the local machine date when writing release notes:

    date '+%Y-%m-%d %H:%M:%S %Z'

Avoid guessing release dates from chat timestamps or UTC-adjacent session logs.

## Repo-local bootstrap helper

For new alpha checkouts, the preferred preparation path is the repo-local bootstrap helper:

    python scripts/bootstrap_repo.py

The bootstrap helper prepares the local checkout without installing system packages, modifying GPU drivers, building llama.cpp, downloading models, or editing shell profiles.

It can create the virtual environment, install Python dependencies, create repo-local runtime directories, copy the example model configuration when needed, initialize the SQLite database, run migrations, and execute the setup diagnostics.

Manual setup remains the explicit reference path and fallback when you want to perform each step yourself.

## Bootstrap validation status

The repo-local bootstrap helper has been validated from a fresh clone.

Validated path:

    git clone git@github.com:WumboLabs/monolith.git
    cd monolith
    python scripts/bootstrap_repo.py
    source .venv/bin/activate
    python scripts/setup_check.py
    python scripts/run_webui.py

Validation covered:

- virtual environment creation
- Python dependency installation from `requirements.txt`
- repo-local runtime directory creation
- `configs/models.yaml` creation from `configs/models.example.yaml`
- SQLite database initialization
- all current migration scripts
- terminal setup diagnostics
- WebUI launch
- `/`, `/setup`, and `/api/setup/status` route smoke tests

Expected first-run warnings remain normal until the user configures local models, llama.cpp paths, and optional LLMGauge imports.


## Clean-clone validation status

A clean-clone install was validated during public-alpha hardening.

Confirmed working:

- Fresh clone from `WumboLabs/monolith`.
- Python virtual environment creation.
- Python dependency installation from `requirements.txt`.
- Local runtime directory creation.
- Example model config copied to `configs/models.yaml`.
- SQLite database initialization.
- Current database migrations.
- `scripts/setup_check.py` completes with warnings but no errors.
- `scripts/run_webui.py` starts the local WebUI.
- Core routes load successfully:
  - `/`
  - `/setup`
  - `/models`
  - `/chat`
  - `/eval`
  - `/context`
  - `/workstation`
  - `/api/setup/status`

Expected clean-clone warnings:

- No configured chat profiles.
- No local GGUF models.
- No llama.cpp binaries.
- No existing run/eval data.
- No local LLMGauge report data.

These warnings are expected in a new environment. They indicate that Monolith is installed but not yet connected to local models, llama.cpp runtimes, or previous evaluation data.
