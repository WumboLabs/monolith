## alpha v0.11.7 - 2026-06-10

- Generalized public-alpha docs and bundled prompt examples.
- Removed remaining original-author machine/path assumptions from active public files.
- Generalized default model, llama.cpp, inventory, and Quant Lab paths.
- Added `docs/PUBLIC_ALPHA.md` with current public-alpha status and limitations.
- Updated troubleshooting database migration instructions.
- Corrected recent release dates to local machine date.

## alpha v0.11.6 - 2026-06-10

- Hardened Workstation system monitoring for other users and machines.
- Added explicit available/error states for CPU, memory, disk, and GPU stats.
- Added root filesystem disk usage to the Workstation page and status ticker.
- Made NVIDIA GPU monitoring optional through nvidia-smi detection.
- Updated Workstation rendering so unavailable metrics show n/a or explanatory notes instead of breaking the page.
- Updated the top system ticker to consume the hardened monitoring payload.

## alpha v0.11.5 - 2026-06-10

- Applied the WumboCore / Monochrome Lime palette to the app theme.
- Reduced high-intensity lime accent opacity for a more restrained workbench look.
- Added a WumboCore refinement override for more neutral charcoal panels and less green wash.
- Removed remaining old Matrix/cyan-green theme wording and color remnants from active CSS.
- Added non-destructive Agent Lab session archiving.
- Hid archived Agent Lab sessions from the default session list.

## alpha v0.11.4 - 2026-06-10

- Added generated SQLite chat profiles for local GGUF models.
- Added Models workflow support for creating chat profiles from local inventory rows.
- Added local model and download job detail pages.
- Added clear-planned-downloads support for planned downloader jobs.
- Added public alpha install/config/downloader/tester/troubleshooting docs.
- Added `requirements.txt` and `.env.example`.
- Added `configs/models.example.yaml` as a public-safe model config template.
- Added `prompts/local/` scaffold for private/user-created prompts.
- Removed hardcoded personal model profile notes from the Chat sidebar.
- Generalized bundled chat prompt text away from machine-specific assumptions.
- Added roadmap note for a future WumboCore / Monochrome Lime theme pass.

# Monolith Changelog

## alpha v0.11.3 - 2026-06-10

### Added
- Added controlled model downloader execution for planned Hugging Face GGUF download jobs.
- Added `POST /api/models/downloads/{job_id}/start` to explicitly start planned downloads.
- Added `.part` file download behavior so final GGUF files only appear after successful completion.
- Added download job status transitions for planned, running, completed, and failed states.
- Added byte progress tracking during active downloads.
- Added automatic local model inventory rescan after completed downloads.
- Added a Download Jobs panel on the Models page.
- Added Start Download buttons for planned and failed jobs.
- Added downloader runtime, progress, transfer-rate, and ETA display fields.
- Added `scripts/test_model_downloader_tiny.py` for safe downloader execution validation without downloading a real model.

### Safety
- Downloads can only start from existing planned or failed jobs.
- Downloads remain restricted to the approved model download root.
- Destination path safety is rechecked before execution.
- Existing final files are not overwritten unless the job explicitly allows overwrite.
- Downloads write to `.part` first and rename only after success.
- Config edits and model execution remain disabled.

### Validation
- Verified a real Hugging Face GGUF download completed successfully.
- Verified `.part` cleanup and final GGUF placement.
- Verified local inventory rescan after completion.
- Verified tiny local downloader integration test passes and cleans up after itself.

## alpha v0.11.2 - 2026-06-10

### Added
- Added controlled model downloader planning schema with the `model_download_jobs` table.
- Added `scripts/migrate_model_downloader.py` as an idempotent SQLite migration.
- Added metadata-only download planning APIs:
  - `GET /api/models/downloads`
  - `POST /api/models/downloads/plan`
- Added approved Hugging Face destination path planning under `~/Monolith/models/huggingface`.
- Added path safety checks for repository-derived directories and GGUF filenames.

### Safety
- Downloader remains planning-only in this milestone.
- No model files are downloaded yet.
- No arbitrary URL textbox is exposed.
- No model config is edited automatically.
- No model execution is triggered after planning.
- `mmproj` files are explicitly excluded from model download planning.

## alpha v0.11.1 - 2026-06-10

Hugging Face GGUF discovery prototype.

### Added
- Added metadata-only Hugging Face GGUF discovery backend.
- Added controlled `GET /api/models/discover/huggingface` endpoint.
- Added stdlib-only Hugging Face API access using `urllib` to avoid new dependency churn.
- Added public model repo search and GGUF sibling extraction.
- Added filename-based family, quant, and architecture guesses for remote GGUF candidates.
- Added case-insensitive local filename matching against the Local GGUF Inventory.
- Added Hugging Face GGUF Discovery section to `/models`.
- Added search form, result table, repo links, and local match badges.

### Validation
- Confirmed `/api/models/discover/huggingface` route registers.
- Confirmed `qwen2.5 3b gguf` search returns 70 GGUF candidates.
- Confirmed 10 local matches for existing Qwen2.5 3B local GGUFs.
- Confirmed `mellum2 gguf` search returns 5 GGUF candidates.
- Confirmed `/models` UI search renders remote GGUF candidates.
- Confirmed no download, config-edit, or model-execution controls are exposed.

### Notes
- File size may show as unknown when Hugging Face repo metadata does not expose size directly.
- Exact remote file size resolution is deferred to the controlled downloader milestone.
- Hugging Face discovery pagination establishes the preferred pattern for future dense tables.
- Future UI/UX polish should convert dense Monolith tables to shared pagination with adjustable page size.
- No downloader added.
- No config editing added.
- No model registration added.
- No model execution added.


## alpha v0.11.0 - 2026-06-10

Model Registry local inventory.

### Added
- Added additive Model Registry migration script: `scripts/migrate_model_registry.py`.
- Added `local_model_files` inventory table for local GGUF tracking.
- Added approved-root local model scanner for:
  - `~/Monolith/models`
  - `~/Monolith/models`
- Added filtering to exclude tiny vocab/support GGUFs and `mmproj` files from the first inventory view.
- Added filename-based family, quant, and architecture guesses.
- Added registration detection against `configs/models.yaml` and `chat_profiles`.
- Added controlled `POST /api/models/local-inventory/scan` endpoint.
- Added Local GGUF Inventory section to `/models`.
- Added scan button for refreshing local inventory from the UI.

### Validation
- Ran migration successfully.
- Confirmed `local_model_files` table exists.
- Scanned approved roots successfully.
- Confirmed 14 real local GGUF model files discovered.
- Confirmed 8 registered and 6 discovered/unregistered models.
- Confirmed `/models` page renders Local GGUF inventory.
- Confirmed scan API works from curl.

### Notes
- No remote search added.
- No downloader added.
- No config editing added.
- No model deletion added.
- No arbitrary path scanning added.
- GPU tuning remains deferred/read-only future work.


## alpha v0.10.2 - 2026-06-10

Agent Backend Eval single-run launcher.

### Added
- Added controlled `POST /api/eval/agent-backend/run-single` endpoint.
- Added active-profile-only Agent Backend Eval single-run validation.
- Added approved `agent-eval-v1` prompt validation with metadata prompt exclusion.
- Added bounded context, max-token, and temperature handling for single eval runs.
- Added llama.cpp execution through existing controlled Monolith runner helpers.
- Added raw output, cleaned output, runtime status, VRAM, and speed metric persistence to `hermes_eval_runs` / `hermes_eval_results`.
- Added current llama.cpp `common_perf_print` parser support for prompt eval and generation throughput.
- Added `/eval/agent-backend` and `/api/eval/agent-backend/options` route aliases while preserving existing `/eval/hermes` compatibility routes.
- Updated Testbench navigation to use the Agent Backend Eval route.
- Corrected public model config example to match current `models` / `chat_profiles` app behavior.

### Validation
- Verified route registration for `/api/eval/agent-backend/run-single`.
- Ran Qwen2.5 3B Q6 8k smoke test against `honesty/no-fake-tool-output.md`.
- Confirmed DB persistence for completed run/result pairs.
- Confirmed parsed metrics from validation run: prompt eval 4201.27 t/s, generation 191.95 t/s, peak VRAM 3333 MiB.

### Notes
- Uses existing `hermes_eval_*` table names for compatibility.
- No automatic scoring added.
- No arbitrary shell, model path, or prompt-root execution added.
- UI launch form and result detail page are deferred.


## alpha v0.10.1 - 2026-06-10

Public repository polish.

### Changed
- Repositioned README around Monolith as a Local AI Workbench.
- Replaced machine-specific README framing with public-facing project language.
- Clarified alpha status, local configuration expectations, security posture, and license status.
- Standardized project version to alpha v0.10.1 across README, VERSION, and app metadata.


## alpha v0.09.2 - 2026-06-09

Matrix terminal theme pass.

### Changed
- Expanded the Testbench tab visual style across the whole app.
- Shifted global palette toward black terminal, Matrix green, and cyan signal accents.
- Increased monospace usage across navigation, tables, forms, badges, metrics, and controls.
- Flattened panels and cards for a more TUI/cyberdeck feel.
- Reduced remaining purple/dark-dashboard styling.
- Tightened table, badge, code, path, and form styling.
- Improved sidebar and system ticker styling to match the terminal theme direction.

### Notes
- CSS-only visual pass.
- No backend changes.
- No database changes.
- No route changes.
- No runner changes.


## alpha v0.09.1 - 2026-06-09

Lab sidebar and Testbench tabs.

### Added
- Added shared Testbench tab partial for Core, Scaling, and Hermes.
- Added tab navigation to `/eval`, `/eval/context-scaling`, and `/eval/hermes`.
- Added terminal-style tab styling.

### Changed
- Renamed sidebar section `Evaluation` to `Lab`.
- Renamed sidebar `Local Eval` item to `Testbench`.
- Removed `Ctx Scaling` and `Hermes Eval` from the sidebar as standalone entries.
- Preserved existing routes for Core, Scaling, and Hermes pages.

### Notes
- Navigation-only/UI-structure change.
- No runner changes.
- No database changes.
- No arbitrary execution paths added.


## alpha v0.09.0 - 2026-06-09

Hermes Backend Eval foundation.

### Added
- Added `core-v3` prompt suite for improved general local model evaluation.
- Added `hermes-v1` prompt suite for Hermes/backend suitability testing.
- Added Hermes Eval database tables:
  - `hermes_eval_runs`
  - `hermes_eval_results`
  - `hermes_eval_scores`
- Added read-only `/eval/hermes` page.
- Added `/api/eval/hermes/options` endpoint.
- Added Hermes Eval sidebar navigation link.
- Added bounded Hermes context ladder metadata including 65536 target context.

### Notes
- No Hermes runner execution yet.
- No arbitrary shell/model path/prompt-root execution added.
- Normal cache remains the first planned evaluation mode.
- Raw-output preservation and manual scoring are prepared in schema but not wired to UI yet.


## alpha v0.08.6 - 2026-06-07

Point release for TUI-style responsive polish.

### Added
- Added responsive runner form layout for Local Eval and Context Scaling.
- Added narrower, more terminal-like table and status pill styling.
- Added smaller-window layout guardrails for Chat.
- Added cleaner model/file path display without heavy black boxes.
- Added horizontal overflow protection for dense tables on narrow windows.
- Added flatter panel/card styling to move the theme toward a TUI/workstation feel.

### Fixed
- Improved Clear stale eval process button sizing/wrapping.
- Reduced oversized category bubble behavior in dense tables.
- Improved Chat page behavior when the window is resized smaller.

### Notes
- CSS-only polish pass.
- No backend changes.
- No schema changes.
- No runner changes.


## alpha v0.08.5 - 2026-06-07

Point release for Monolith theme baseline.

### Added
- Added restrained dark Matrix/cyberpunk workstation CSS theme layer.
- Added explicit Monolith-native theme tokens for black/graphite surfaces, cyan-green accents, text, borders, and restrained glow.
- Added subtle background grid/ambient glow treatment.
- Added consistent panel, card, table, button, status pill, code block, and output styling.
- Added accessibility-aware reduced-motion handling.

### Notes
- CSS-only theme baseline.
- No backend changes.
- No schema changes.
- No runner changes.
- Design goal is a serious local AI control room: darker, sharper, technical, and slightly mysterious without Rosé Pine/pastel dominance or harsh neon overload.


## alpha v0.08.4 - 2026-06-07

Point release for Context dashboard integration.

### Added
- Added controlled Context Scaling summary data to `/context`.
- Added controlled runs/results/max-context/max-peak-VRAM cards.
- Added VRAM fit summary table grouped by context size.
- Added latest controlled context-scaling results table.
- Added links from `/context` to Context Scaling run details.

### Notes
- No runner changes.
- No database schema changes.
- No arbitrary execution changes.
- This is dashboard/read-only integration only.


## alpha v0.08.3 - 2026-06-07

Point release for Context Scaling peak VRAM capture.

### Added
- Added system-level NVIDIA VRAM sampler for Context Scaling subprocesses.
- Added peak VRAM storage in `context_scaling_results.peak_vram_mb`.
- Added peak VRAM capture for successful and failed context-scaling prompt runs.
- Added live Peak VRAM display in the Context Scaling task status panel.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- VRAM capture is system-level GPU memory used, suitable for practical fit testing while controlled runs execute one at a time.
- Per-process VRAM attribution may be added later if needed.


## alpha v0.08.2 - 2026-06-07

Point release for Context Scaling safety controls.

### Added
- Added Clear stale eval process button to Context Scaling.
- Reused existing `/api/eval/cleanup-stale` cleanup endpoint from Local Eval.
- Added Context Scaling cleanup status output and refresh behavior.
- Added cleanup button disable/reenable behavior during active context-scaling runs.

### Changed
- Updated Context Scaling page copy from shell/planned wording to controlled active workflow wording.
- Removed obsolete next-step panel now that execution is wired.
- Kept Stop run behavior on the shared eval task abort endpoint.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- No arbitrary shell commands.
- No arbitrary model paths.
- No arbitrary prompt roots.
- Cleanup remains limited to eval-like Quant Lab / llama-cli processes.


## alpha v0.08.1 - 2026-06-07

Point release for controlled Context Scaling execution.

### Added
- Added `POST /api/eval/context-scaling/run`.
- Added `GET /api/eval/context-scaling/tasks/{task_id}`.
- Added controlled Context Scaling background worker.
- Added Context Scaling launch form on `/eval/context-scaling`.
- Added task progress display for context-scaling runs.
- Added controlled loop over approved context sizes and approved prompt files.
- Added import/copy path from Quant Lab reports into `context_scaling_results`.
- Added automatic redirect to `/eval/context-scaling/{run_id}` after completion.

### Notes
- Uses existing known-good Quant Lab runner.
- No arbitrary shell commands.
- No arbitrary model paths.
- No arbitrary prompt roots.
- Normal/stable cache mode only.
- Raw output is preserved.
- Scoring is not implemented yet.


## alpha v0.08.0 - 2026-06-07

Feature foundation for Context Scaling.

### Added
- Added `context_scaling_runs` SQLite table.
- Added `context_scaling_results` SQLite table.
- Added `scripts/migrate_context_scaling.py`.
- Added `/eval/context-scaling` read-only page shell.
- Added `/eval/context-scaling/{run_id}` placeholder detail page.
- Added `GET /api/eval/context-scaling/options`.
- Added sidebar navigation link for Context Scaling.
- Added default context ladder metadata: 8192, 12288, 16384.
- Added optional extended ladder metadata: 24576, 32768.
- Added approved default prompt subset for future context-scaling runs.

### Notes
- Execution is intentionally not enabled yet.
- No Quant Lab runner changes.
- No arbitrary shell commands.
- No arbitrary model paths.
- No arbitrary prompt roots.
- This milestone is schema and UI foundation only.


## alpha v0.07.5 - 2026-06-07

Point release for clean Local Eval output display.

### Added
- Added display-only clean output previews for imported Quant Lab prompt results.
- Raw imported output remains preserved unchanged.
- Cleaned output hides obvious llama.cpp startup/banner/prompt-wrapper noise where possible.
- Raw captured output remains available behind a details toggle.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- No stored output mutation.
- Cleaner is display-only and conservative.


## alpha v0.07.4 - 2026-06-07

Point release for Local Eval stale process cleanup.

### Added
- Added `POST /api/eval/cleanup-stale`.
- Added Clear stale eval process button to Local Eval.
- Added process-group termination helper with SIGTERM then SIGKILL fallback.
- Strengthened abort cleanup for controlled Local Eval runner processes.

### Changed
- Stop run now uses stronger process-group cleanup.
- Stale cleanup targets only eval-like `run-core-v2-suite.sh` and `llama-cli` processes matching Quant Lab/core-v2/single-turn execution patterns.

### Notes
- This does not kill arbitrary GPU processes.
- This does not change the Quant Lab runner.
- No database schema changes.
- No arbitrary execution behavior added.


## alpha v0.07.3 - 2026-06-06

Point release for Local Eval abort refresh polish.

### Changed
- Local Eval now refreshes automatically after an aborted task reaches terminal state.
- Abort flow now mirrors completed-run behavior: show a short terminal message, then update the page.
- Failed tasks still remain visible without auto-refresh for troubleshooting.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- No arbitrary execution behavior added.


## alpha v0.07.2 - 2026-06-06

Point release for Local Eval abort control.

### Added
- Added Stop run button next to the Local Eval Run suite button.
- Added `/api/eval/tasks/{task_id}/abort`.
- Added background process tracking for active Local Eval subprocesses.
- Abort requests terminate the Quant Lab runner process group.
- Aborted tasks are marked with `status=aborted` and `exit_code=-15` where applicable.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- No arbitrary execution behavior added.
- Abort state is task-state level for now, not persistent historical run logging.


## alpha v0.07.1 - 2026-06-06

Point release for Local Eval completion redirect / auto-refresh polish.

### Changed
- Added automatic redirect after controlled core-v2 Local Eval tasks complete.
- Completed tasks now expose `suite_run_id`, `import_id`, and `result_url` aliases in addition to the existing imported result fields.
- Frontend polling now opens the imported result page after a short completion delay.
- If no result URL is available, the Local Eval page refreshes instead.

### Notes
- No Quant Lab runner changes.
- No database schema changes.
- No arbitrary execution behavior added.



## alpha v0.07 - 2026-06-06

Feature milestone for controlled Local Eval suite execution.

### Added
- Added Local Eval Run core-v2 suite form.
- Added `/api/eval/run-core-v2` task start endpoint.
- Added `/api/eval/tasks/{task_id}` task status endpoint.
- Added background Quant Lab runner subprocess execution.
- Added basic task progress, elapsed time, ETA, current item, stdout tail, and completion link.
- Added import-on-success using the existing Quant Lab core-v2 importer.
- Limited runner inputs to active Monolith profiles, approved core-v2 categories, and bounded numeric settings.

### Notes
- Execution uses the known-good Quant Lab runner.
- Arbitrary shell commands are not accepted.
- Arbitrary prompt roots are not accepted.
- Generated reports are imported into the existing Quant Lab import tables.


## alpha v0.06.1 - 2026-06-06

Point release for Local Eval imported Quant Lab run visibility.

### Added
- Added imported Quant Lab run summary to `/eval`.
- Added `/eval/imports/{suite_run_id}` detail pages.
- Added imported suite metadata display.
- Added per-prompt result table with capture status and speed metrics.
- Added collapsible output previews for imported prompt results.

### Notes
- Read-only viewer only.
- No model execution from Monolith.
- No scoring changes.
- No existing table changes.


## alpha v0.06 - 2026-06-06

Feature milestone for Quant Lab core-v2 import foundation.

### Added
- Added `scripts/import-quant-lab-core-v2.py`.
- Added additive SQLite tables:
  - `quant_lab_suite_runs`
  - `quant_lab_prompt_results`
- Added import support for Quant Lab core-v2 Markdown suite reports.
- Stored suite metadata, source report path, source report SHA256, model metadata, prompt sections, output text, and speed metrics.
- Added safe re-import behavior by `source_report_path`.

### Notes
- No model execution from Monolith yet.
- No Local Eval UI for imported runs yet.
- Existing `runs`, `scores`, and `benchmarks` tables are unchanged.


## alpha v0.05.1 - 2026-06-06

Point release for Local Eval prompt metadata polish.

### Changed
- Added category metadata for the core-v2 Local Eval prompt suite.
- Added prompt title extraction from Markdown headings.
- Added prompt summary extraction from prompt content.
- Added category purpose, scoring emphasis, and risk labels.
- Improved `/eval` with evaluation philosophy and category cards.
- Improved prompt detail pages with purpose and scoring emphasis sections.
- Added future ETA/progress tracking note to Local Eval guardrails.

### Notes
- No model execution.
- No prompt editing.
- No database schema changes.


## alpha v0.05 - 2026-06-06

Feature milestone for Local Eval / Prompt Library foundation.

### Added
- Added Monolith-owned `prompts/core-v2/` prompt suite.
- Added `/eval` Local Eval page.
- Added read-only prompt library loader.
- Added prompt category and prompt file tables.
- Added `/eval/prompts/{category}/{filename}` prompt detail pages.
- Added Local Eval sidebar navigation item.
- Added read-only guardrails for future evaluation work.

### Notes
- No model execution yet.
- No prompt editing yet.
- No database schema changes.
- This is the foundation for future structured local model evaluation.


## alpha v0.04.5 - 2026-06-05

Point release for Dashboard readability.

### Changed
- Reworked Dashboard into a compact run-health overview.
- Added success, failure, scored, and unscored counts.
- Added latest successful run card.
- Added latest failed run card.
- Added compact recent activity table.
- Preserved context run family summary with a link to the Context page.
- Kept Dashboard as a summary page rather than duplicating the full Runs page.

### Notes
- No database schema changes.
- No model runtime changes.
- Dashboard now better reflects the run/failure/scoring data added during the v0.04.x polish series.


## alpha v0.04.4 - 2026-06-05

Point release for Run detail readability.

### Changed
- Polished `/runs/{id}` detail pages.
- Added OK/FAILED and scored/unscored status badges near the page title.
- Added compact profile, category, context, speed, VRAM, and trust summary cards.
- Added file link strip for prompt, response, and raw log files.
- Added failure alert box for failed runs.
- Improved response and prompt display with scrollable preformatted blocks.
- Improved latest score summary display.
- Preserved full metadata table lower on the page.

### Notes
- No database schema changes.
- No model runtime changes.
- Manual scoring behavior is unchanged.


## alpha v0.04.3 - 2026-06-05

Point release for Models page readability.

### Changed
- Split `/models` into Chat Profiles and Catalog Models sections.
- Added active, experimental, found, missing, and downloader-disabled badges.
- Added clearer runtime/profile metadata for runnable chat profiles.
- Added compact local file path display with full path available as a tooltip.
- Added compact notes and tag display.
- Preserved read-only registry policy.

### Notes
- No database schema changes.
- No model runtime changes.
- No downloader implementation.
- Model Registry remains read-only.


## alpha v0.04.2 - 2026-06-05

Point release for Runs page visibility and failure-log usability.

### Changed
- Polished `/runs` table layout.
- Added OK/FAILED status pills.
- Added scored/unscored status pills.
- Added prompt category badges.
- Added subtle failed-row tint.
- Added quick links for raw logs and response reports when present.
- Added clearer model/profile display.
- Added compact token, speed, wall-time, and VRAM display.

### Notes
- No database schema changes.
- No model runtime changes.
- This exposes the failure logging added and validated during alpha v0.04.1 work.


## alpha v0.04.1 - 2026-06-05

Point release for small UI/layout polish after the alpha v0.04 Model Registry milestone.

### Changed
- Removed duplicate main-panel Monolith branding from the top header.
- Moved the system ticker to the top of the main content area.
- Kept persistent branding in the sidebar only.
- Preserved sidebar footer version display.
- Continued Chat page layout polish from v0.04.
- Expanded active Chat model profiles through the registry.
- Validated failed Chat run logging with `chat-web-failed` rows.

### Notes
- No database schema changes.
- No model downloader implemented.
- Model Registry remains read-only.
- Failure logging is now validated with a controlled missing-model test.


## alpha v0.04 - 2026-06-05

Feature milestone for the read-only Model Registry.

### Added
- `configs/models.yaml` now includes active Chat profile definitions.
- Model registry loader in the FastAPI backend.
- Read-only `/models` page.
- Sidebar link for Models.
- Chat model selector now populates from registry-provided active profiles.
- Local model file found/missing status on the Models page.
- Placeholder source/download metadata fields for future downloader support.

### Notes
- No model downloader is implemented yet.
- No database schema changes.
- No model execution behavior should change.
- Existing chat profile keys are preserved.


## alpha v0.03.1 - 2026-06-05

Patch release for Chat page UI/UX helper text.

### Added
- Inline mode description under the Chat mode selector.
- Compact Modes reference table in the Chat sidebar.
- Reusable helper text CSS classes for future UI polish.

### Changed
- Updated app display version to `alpha v0.03.1`.

### Notes
- No backend scoring changes.
- No database schema changes.
- No model runtime changes.


## alpha v0.03 - 2026-06-04

Feature milestone for manual run scoring from the dashboard.

### Added
- Score form on run detail pages.
- Score API route at `/api/runs/{run_id}/score`.
- Manual scoring support using the existing `scores` table.
- Latest score display on run detail pages.
- Prompt and response preview on run detail pages.

### Notes
- Scoring is manual only.
- LLM-as-judge is intentionally not implemented.
- Multiple score submissions create additional score rows; the latest score is displayed.


## alpha v0.02.2 - 2026-06-04

Patch release for sidebar and system-status UI polish.

### Added
- Collapsible sidebar with browser-local saved state.
- Compact scrolling system status ticker.
- Dedicated Workstation page at `/workstation`.
- Active sidebar link highlighting.

### Changed
- Replaced large workstation status card strip with compact ticker.
- Workstation sidebar item is now a real route.
- Updated app display version to `alpha v0.02.2`.


## alpha v0.02.1 - 2026-06-04

Patch release for post-v0.02 UI/versioning polish.

### Changed
- Established versioning scheme:
  - `alpha v0.02` = milestone baseline
  - `alpha v0.02.x` = small patch, UX/UI polish, or bugfix
  - `alpha v0.03` = next feature milestone
- Updated app display version to `alpha v0.02.1`.
- Added root `VERSION` file.
- Kept `alpha v0.02` as the known-good repaired Monolith baseline.

### Current baseline
- FastAPI/Jinja dashboard works.
- Sidebar and Monolith branding work.
- Overview, Context, Runs, Run Detail, and Chat pages work.
- Manual and auto-save chat run logging work.
- `llama-tokenize` token counts work for new chat saves.
- Peak VRAM capture works for new chat saves.
- SQLite run logging works.

## alpha v0.02 - 2026-06-04

Known-good Monolith baseline after project rename and repair.

### Added
- Project renamed to Monolith.
- Clean app branding: Monolith / Local AI Workbench.
- Sidebar sections: Main, Evaluation, System.
- Version footer.
- Verified backup: `monolith-alpha-v0.02.tar.gz`.

### Fixed
- Restored all core routes and helpers.
- Restored chat save backend.
- Restored run logging.
- Restored token and VRAM metadata path.
