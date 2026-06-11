# Troubleshooting

## Monolith will not start

Verify dependencies:

    source .venv/bin/activate
    pip install -r requirements.txt

Run compile check:

    python -m compileall dashboard_fastapi scripts

## Database missing

Run:

    python scripts/init_db.py
    python scripts/migrate_model_registry.py
    python scripts/migrate_model_downloader.py
    python scripts/migrate_generated_chat_profiles.py
    python scripts/migrate_context_scaling.py
    python scripts/migrate_hermes_eval.py
    python scripts/migrate_agent_lab.py

## Model does not appear in Chat

Open `/models`.

Check:

- model appears in Local GGUF inventory
- model file exists
- click "Create chat profile"
- reload `/chat`

Generated profiles are stored in SQLite, not `configs/models.yaml`.

## Chat errors with llama.cpp flag

Check the profile `extra_args`.

For generated profiles, `extra_args` should usually be empty:

    extra_args: []

Only add advanced flags after verifying your llama.cpp binary supports them.

## Download stays planned

Click "Start download" from `/models`.

If you want to remove planned jobs, use "Clear planned downloads".

## Download failed

Open the download job detail page:

    /models/downloads/<id>

Review:

- source URL
- destination path
- error text
- notes

## Local prompts

Put private or machine-specific prompts under:

    prompts/local/

Files under `prompts/local/` are ignored by git except the scaffold README and `.gitkeep` files.
