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

`scripts/run_webui.py` loads `.env` automatically before starting the WebUI. If you start uvicorn directly or use a service wrapper, export the variables in that shell or service wrapper.

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
