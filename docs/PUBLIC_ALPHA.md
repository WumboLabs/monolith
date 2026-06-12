# Public Alpha Status

Monolith is currently a technical public alpha for Linux users who are comfortable with local model runtimes, GGUF files, Python virtual environments, and llama.cpp.

It is not yet packaged as a general-purpose desktop app or one-command installer.

## Current version

    alpha v0.11.9

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
