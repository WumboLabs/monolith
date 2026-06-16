# LLMGauge Import Architecture

Monolith will consume LLMGauge artifacts as a UI/operator layer. LLMGauge remains the evaluation engine.

This document defines the initial Monolith-side import boundary for LLMGauge v0.13 artifacts.

## Boundary

LLMGauge owns:

- prompt suite schema and validation
- llama.cpp / GGUF execution
- result directory creation
- raw prompt/output/log artifact capture
- context ladder execution
- manual scoring files
- comparison reports
- export indexes
- artifact validation

Monolith owns:

- UI navigation
- local import/index state
- artifact browsing
- result summaries
- setup diagnostics
- model/profile operator context
- optional controlled launch state in a later milestone

LLMGauge must not write directly into the Monolith SQLite database.

The first supported contract is:

    LLMGauge filesystem artifacts -> Monolith importer -> Monolith DB/UI

## Supported LLMGauge v0.13 artifact inputs

The initial importer should support:

1. A single run directory

       llmgauge-result.json
       report.md
       raw/
       logs/

2. A context ladder directory

       ladder-summary.json
       ladder-report.md
       ctx-8192/
       ctx-12288/
       ctx-16384/

   Each `ctx-*` child is a normal single run directory.

3. An export index

       llmgauge-index.json

The export index schema is:

    llmgauge.export_index.v0

The currently documented artifact schemas are:

- `llmgauge.result.v0`
- `llmgauge.context_ladder.v0`
- `llmgauge.context_prompt.v0`
- `llmgauge.suite.v0`
- `llmgauge.export_index.v0`

## Initial import behavior

The first Monolith importer should be read-only with respect to source artifacts.

It should:

- accept a run directory, ladder directory, or `llmgauge-index.json`
- detect artifact type
- validate where practical
- store source path
- store artifact type
- store schema version
- store import timestamp
- store validation status
- store validation errors
- store summary metadata
- store references to report/raw/log files
- avoid copying raw artifacts by default

It should not:

- launch LLMGauge
- execute arbitrary shell commands
- accept arbitrary model or prompt paths from the UI
- mutate LLMGauge result directories
- delete old Quant Lab, context scaling, Hermes Eval, or Agent Lab rows

## Legacy compatibility

These existing Monolith systems must remain intact:

- `quant_lab_suite_runs`
- `quant_lab_prompt_results`
- `context_scaling_runs`
- `context_scaling_results`
- `hermes_eval_runs`
- `hermes_eval_results`
- `hermes_eval_scores`
- `agent_sessions`
- `agent_plans`
- `agent_action_proposals`
- `agent_reviews`

Existing routes must remain intact:

- `/eval`
- `/eval/imports/{id}`
- `/eval/prompts/{category}/{filename}`
- `/context`
- `/eval/context-scaling`
- `/eval/context-scaling/{id}`

Existing APIs must remain intact:

- `POST /api/eval/run-core-v2`
- `GET /api/eval/tasks/{task_id}`
- existing context-scaling APIs

Existing scripts must remain intact:

- `scripts/import-quant-lab-core-v2.py`
- `scripts/migrate_context_scaling.py`
- `scripts/migrate_hermes_eval.py`
- `scripts/migrate_agent_lab.py`

Do not rename or drop legacy tables in the first LLMGauge import milestone.

## Recommended additive tables

The first migration should add new tables rather than reuse legacy tables.

Suggested tables:

### `llmgauge_artifact_imports`

Purpose: one row per imported LLMGauge run or ladder artifact.

Suggested fields:

- `id`
- `artifact_type`
- `source_path`
- `source_path_kind`
- `source_hash`
- `schema_version`
- `imported_at_utc`
- `validation_checked`
- `validation_status`
- `validation_errors_json`
- `artifact_json`
- `result_json_path`
- `report_path`
- `ladder_summary_path`
- `ladder_report_path`
- `raw_dir_path`
- `logs_dir_path`

### `llmgauge_run_summaries`

Purpose: summary metadata for imported single-run artifacts.

Suggested fields:

- `import_id`
- `run_id`
- `status`
- `timestamp_utc`
- `suite_id`
- `suite_version`
- `model_id`
- `model_profile_json`
- `prompt_count`
- `completed`
- `failed`
- `manual_score_total`
- `manual_score_max`
- `has_raw_artifacts`
- `has_logs`

### `llmgauge_ladder_summaries`

Purpose: summary metadata for imported ladder artifacts.

Suggested fields:

- `import_id`
- `ladder_id`
- `suite_id`
- `model_id`
- `include_json`
- `only_json`
- `contexts_json`
- `child_run_count`
- `completed`
- `failed`
- `total`
- `has_child_runs`

## Initial importer script

Initial script name:

    scripts/import_llmgauge_results.py

Supported usage:

    python scripts/import_llmgauge_results.py /path/to/run-dir
    python scripts/import_llmgauge_results.py /path/to/ladder-dir
    python scripts/import_llmgauge_results.py /path/to/llmgauge-index.json

Detection:

- directory with `llmgauge-result.json` -> run
- directory with `ladder-summary.json` -> ladder
- file named `llmgauge-index.json` -> export index

Validation:

- for direct run dirs, optionally call `llmgauge validate-result`
- for direct ladder dirs, optionally call `llmgauge validate-ladder`
- for export indexes, record embedded validation metadata if present
- if LLMGauge validation command is unavailable, perform schema-lite JSON parsing and mark validation accordingly

## UI direction

First UI milestone should be read-only.

Possible route:

    /eval/llmgauge

Possible detail route:

    /eval/llmgauge/imports/{id}

Initial UI should show:

- imported artifact list
- artifact type
- validation status
- suite/model/status/completed/failed
- report path
- raw/log artifact references
- ladder child contexts
- manual score totals if present

Do not add launch controls in the first import milestone.

## Setup diagnostics

Add optional detection for:

    MONOLITH_LLMGAUGE_ROOT

Keep legacy compatibility with:

    MONOLITH_QUANT_LAB_ROOT

Recommended resolution order:

1. `MONOLITH_LLMGAUGE_ROOT`
2. `MONOLITH_QUANT_LAB_ROOT`
3. default fallback if any

Missing LLMGauge root should remain a warning, not an error, unless the user is actively importing LLMGauge artifacts.

## Migration sequence

1. Add this architecture document.
2. Add additive `llmgauge_*` migration.
3. Add `scripts/import_llmgauge_results.py`.
4. Validate importer against:
   - one real run directory
   - one real ladder directory
   - one `llmgauge-index.json`
5. Add read-only `/eval/llmgauge` listing.
6. Add read-only LLMGauge import detail page.
7. Keep legacy Quant Lab/core-v2/Hermes/context views working.
8. Only after import flow is stable, plan controlled LLMGauge launch UI.

## Safety rule

LLMGauge artifacts are the portable audit source for what was run.

Monolith imports and indexes those artifacts for UI display.

Do not make Monolith an arbitrary command runner.
