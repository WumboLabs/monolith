# Monolith alpha install

Monolith is a local AI workbench for running, tracking, downloading, and evaluating local GGUF models.

This alpha release is intended for technical users who already understand local model runtimes.

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

    uvicorn dashboard_fastapi.app:app --host 127.0.0.1 --port 8000

Open:

    http://127.0.0.1:8000

Open setup diagnostics:

    http://127.0.0.1:8000/setup

Raw setup diagnostics JSON:

    http://127.0.0.1:8000/api/setup/status

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
