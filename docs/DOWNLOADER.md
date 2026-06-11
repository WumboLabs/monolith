# Model downloader

Monolith includes a controlled Hugging Face GGUF downloader.

## Safety model

The downloader is intentionally limited:

- Hugging Face GGUF metadata only
- approved download root only
- `.part` file during transfer
- final rename after completion
- no automatic model execution
- no automatic config edits
- no arbitrary shell commands

## Default download root

    ~/Monolith/models/huggingface

Override with:

    MONOLITH_MODEL_DOWNLOAD_ROOT=/path/to/models/huggingface

Downloaded files are placed under:

    <download-root>/<owner>--<repo>/<filename>.gguf

Example:

    ~/Monolith/models/huggingface/LiquidAI--LFM2.5-8B-A1B-GGUF/LFM2.5-8B-A1B-Q4_0.gguf

## Workflow

1. Open `/models`
2. Search Hugging Face GGUF models
3. Click "Plan download"
4. Review the planned job
5. Click "Start download"
6. Wait for completion
7. Use local inventory to create a chat profile

## Download jobs

Download jobs can be viewed from `/models`.

Completed jobs are preserved as history.

Planned jobs can be cleared with "Clear planned downloads".

Running and completed jobs are not affected by clearing planned jobs.

## Detail pages

Local model detail page:

    /models/local/<id>

Download job detail page:

    /models/downloads/<id>
