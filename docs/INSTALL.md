# Monolith alpha install

Monolith is a local AI workbench for running, tracking, downloading, and evaluating local GGUF models.

This alpha release is intended for technical users who already understand local model runtimes.

## Repo-local bootstrap helper

Monolith includes a conservative repo-local bootstrap helper:

    python scripts/bootstrap_repo.py

The bootstrap helper prepares a cloned checkout without mutating system-level dependencies.

It can:

- create `.venv` if missing
- install `requirements.txt` into `.venv`
- create repo-local runtime directories
- copy `configs/models.example.yaml` to `configs/models.yaml` only when missing
- run database initialization and migration scripts
- run `scripts/setup_check.py`

It does not:

- use `sudo`
- install GPU drivers
- install CUDA or ROCm
- build llama.cpp
- download models by default
- edit shell profiles
- modify system package manager state

Useful options:

    python scripts/bootstrap_repo.py --dry-run
    python scripts/bootstrap_repo.py --skip-pip
    python scripts/bootstrap_repo.py --skip-db
    python scripts/bootstrap_repo.py --skip-setup-check

`--force-config` overwrites `configs/models.yaml` from the example config and requires `--yes`.

    python scripts/bootstrap_repo.py --force-config --yes


## Supported alpha install path

Use the direct local Python install.

Docker is not the recommended public-alpha path yet.

## Requirements

- Linux workstation
- Python 3.11 or newer
- Git
- SQLite
- A local llama.cpp build for chat/eval execution
- Local GGUF models, or use Monolith's Hugging Face GGUF downloader

Monolith does not install llama.cpp, GPU drivers, CUDA, ROCm, or model runtimes for you.

## Clone

    git clone https://github.com/WumboLabs/monolith.git
    cd monolith

## Create virtual environment

    python -m venv .venv
    source .venv/bin/activate

## Install Python dependencies

    pip install -r requirements.txt

## Create local directories

    mkdir -p "$HOME/Monolith/models/huggingface"

## Configure models

Start from the example config:

    cp configs/models.example.yaml configs/models.yaml

Edit:

    configs/models.yaml

Set your local llama.cpp launcher path and GGUF model path.

Example fields to update:

    launcher: /home/YOUR_USER/Monolith/llama.cpp/build/bin/llama-cli
    model: /home/YOUR_USER/Monolith/models/huggingface/OWNER--REPO/model-file.gguf

## Initialize database

    python scripts/init_db.py
    python scripts/migrate_model_registry.py
    python scripts/migrate_model_downloader.py
    python scripts/migrate_generated_chat_profiles.py
    python scripts/migrate_context_scaling.py
    python scripts/migrate_hermes_eval.py
    python scripts/migrate_agent_lab.py

## Check setup status

Run the read-only setup checker:

    python scripts/setup_check.py

Optional JSON output:

    python scripts/setup_check.py --json

Strict mode returns non-zero only when setup errors are present:

    python scripts/setup_check.py --strict

Warnings are allowed during alpha setup. For example, a machine may not have local GGUF files yet or may use a llama.cpp path outside the default example path.

## Start Monolith

    python scripts/run_webui.py

Open:

    http://127.0.0.1:8765

Open setup diagnostics:

    http://127.0.0.1:8765/setup

Raw setup diagnostics JSON:

    http://127.0.0.1:8765/api/setup/status

## First useful workflow

1. Open `/setup` and review errors or warnings
2. Open `/models`
3. Search Hugging Face for a GGUF model
4. Plan and start a controlled download
5. Scan local inventory if needed
6. Click "Create chat profile" on a local model
7. Open `/chat`
8. Select the generated profile and test the model

## Alpha limitations

- No automatic llama.cpp installation
- No automatic GPU setup
- No full profile editor yet
- No automatic tuning of llama.cpp flags
- Docker is not the primary public-alpha install path
- Local/private prompts belong in `prompts/local/`
