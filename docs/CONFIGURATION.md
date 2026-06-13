# Monolith configuration

Monolith uses local files and environment variables for alpha configuration.

## Main config files

    configs/models.yaml
    .env.example
    data/llm-tests.sqlite

## Environment variables

Monolith supports these optional overrides:

    MONOLITH_DB_PATH
    MONOLITH_MODELS_CONFIG
    MONOLITH_MODEL_INVENTORY_ROOTS
    MONOLITH_MODEL_DOWNLOAD_ROOT
    MONOLITH_QUANT_LAB_ROOT

Defaults:

    MONOLITH_DB_PATH=./data/llm-tests.sqlite
    MONOLITH_MODELS_CONFIG=./configs/models.yaml
    MONOLITH_MODEL_INVENTORY_ROOTS=~/Monolith/models
    MONOLITH_MODEL_DOWNLOAD_ROOT=~/Monolith/models/huggingface
    MONOLITH_QUANT_LAB_ROOT=./quant-lab

LLMGauge is the public-facing name for this evaluation workflow. `MONOLITH_QUANT_LAB_ROOT` and `quant-lab` remain legacy/local integration names for now.

### WebUI host and port

`scripts/run_webui.py` loads `.env` automatically before starting the local WebUI.

Supported WebUI variables:

- `MONOLITH_WEB_HOST` — default `127.0.0.1`
- `MONOLITH_WEB_PORT` — default `8765`

The canonical local development URL is:

    http://127.0.0.1:8765/

If you start uvicorn directly or use a service wrapper, export the variables in that shell or service wrapper.


## Model config

Start with:

    cp configs/models.example.yaml configs/models.yaml

A basic chat profile needs:

    launcher
    model
    ctx_size
    batch_size
    ubatch_size
    gpu_layers
    temperature
    max_tokens

Example:

    chat_profiles:
      example-local-gguf-chat:
        label: Example Local GGUF Chat
        active: true
        launcher: /home/YOUR_USER/Monolith/llama.cpp/build/bin/llama-cli
        model: /home/YOUR_USER/Monolith/models/huggingface/OWNER--REPO/model-file.gguf
        ctx_size: 8192
        batch_size: 256
        ubatch_size: 64
        gpu_layers: 999
        temperature: 0.2
        max_tokens: 800
        extra_args: []

## Advanced llama.cpp flags

Use `extra_args` as a YAML list.

Good:

    extra_args:
      - --some-flag
      - value

Avoid shell strings:

    extra_args: "--some-flag value"

Leave `extra_args` empty unless you have verified the flag works with your llama.cpp binary.

## Generated chat profiles

The Models page can create generated chat profiles from local GGUF inventory rows.

Generated profiles are stored in SQLite:

    generated_chat_profiles

They do not edit `configs/models.yaml`.

This is the preferred alpha workflow for downloaded models.

## GPU diagnostics

Monolith can detect NVIDIA GPU readiness through `nvidia-smi` when it is available.

Setup diagnostics report:

- whether `nvidia-smi` is available
- visible NVIDIA GPU name
- NVIDIA driver version
- total reported VRAM

Monolith does not install or modify GPU drivers, CUDA packages, kernel modules, Secure Boot settings, or system package manager state. GPU driver/runtime setup remains an external platform prerequisite.


## llama.cpp runtime paths

Monolith does not require llama.cpp to be built inside the Monolith repository.

There are two ways llama.cpp paths are used:

- model profiles can define a `launcher` path for running a specific model
- environment variables can define fallback/runtime helper paths used by setup diagnostics, token counting, and generated/runtime workflows

If you already built llama.cpp elsewhere, keep it where it is and point Monolith at it.

Example `.env` values:

    MONOLITH_LLAMA_COMPLETION=$HOME/Projects/local-llm/llama.cpp/build/bin/llama-cli
    MONOLITH_LLAMA_TOKENIZE=$HOME/Projects/local-llm/llama.cpp/build/bin/llama-tokenize

Notes:

- `MONOLITH_LLAMA_COMPLETION` is the current legacy environment variable name for the configured llama.cpp generation binary.
- In newer llama.cpp builds, this will usually point at `llama-cli`.
- `MONOLITH_LLAMA_TOKENIZE` should point at `llama-tokenize`.
- Setup diagnostics report whether these paths come from explicit environment variables or default fallback paths.
