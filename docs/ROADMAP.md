# Monolith Roadmap

This roadmap tracks near-term public-alpha work. It is intentionally conservative: improve portability, safety, documentation, and local usability before adding larger automation features.

## Completed recent milestones

### alpha v0.11.4 — public-alpha readiness

- Generated local chat profiles from discovered GGUF models.
- Added local model detail pages.
- Added public install/configuration/troubleshooting docs.
- Added `.env.example`, `requirements.txt`, and sanitized example model config.
- Added `prompts/local/` as the intended home for private/user-created prompts.

### alpha v0.11.5 — WumboCore / Monochrome Lime theme pass

- Applied the WumboCore / Monochrome Lime visual system.
- Reduced high-intensity lime accent wash.
- Refined the workbench contrast layer.
- Added non-destructive Agent Lab session archiving.

### alpha v0.11.6 — portable Workstation monitoring

- Hardened Workstation monitoring fallbacks.
- Added explicit available/error states for CPU, memory, disk, and GPU metrics.
- Added root disk usage to Workstation and the top system ticker.
- Made NVIDIA monitoring optional through `nvidia-smi` detection.

### alpha v0.11.7 — public-alpha generic install audit

- Generalized public-alpha docs and bundled prompt examples.
- Removed remaining original-author machine/path assumptions from active public files.
- Generalized default model, llama.cpp, inventory, and evaluation workflow paths.
- Added `docs/PUBLIC_ALPHA.md` with current public-alpha status and limitations.
- Updated troubleshooting database migration instructions.
- Corrected recent release dates to local machine date.

### alpha v0.11.8 — first-run and setup hardening

- Added read-only setup diagnostics at `/setup`.
- Added raw setup diagnostics JSON at `/api/setup/status`.
- Added `scripts/setup_check.py` for terminal-side setup validation.
- Improved first-run empty states on `/models`, `/chat`, and `/eval`.
- Documented setup diagnostics in install, troubleshooting, and public-alpha docs.

### alpha v0.11.9 — terminal workbench UI shell

- Added a coherent workbench UI concept document.
- Locked local WebUI startup to `scripts/run_webui.py` and `http://127.0.0.1:8765/`.
- Refined the global shell, sidebar, status ticker, cards, panels, and tables.
- Added shared table pagination with a 5-row default and adjustable row limits.
- Added active tab highlighting and terminal-readable typography.
- Preserved existing routes, workflows, and conservative safety boundaries.
- Deferred deeper multi-pane/TUI behavior to a later polish milestone.

## Current milestone

### alpha v0.11.10 — clean-clone install validation and release hardening

Goal: validate the public-alpha install path from a clean clone after the v0.11.9 UI shell baseline.

Planned work:

- Run a clean-clone install test from the documented public-alpha path.
- Capture any missing dependency, migration, setup, or documentation gaps.
- Verify the fixed `scripts/run_webui.py` launcher and `http://127.0.0.1:8765/` WebUI path.
- Tighten install, configuration, troubleshooting, and public-alpha docs based on real clean-clone notes.
- Consider lightweight GitHub issue templates if Issues are enabled.

## Later candidates

### Packaging

- Add a more formal install path.
- Consider a `pyproject.toml`.
- Add a safer first-run setup command.
- Add dependency version guidance or lockfile strategy.

### Model setup

- Improve model discovery onboarding.
- Add clearer empty-state UI when no GGUF models are configured.
- Improve downloader documentation and recovery flows.

### Local Eval / LLMGauge

- Improve scoring UI.
- Improve run comparison views.
- Add safer import/export flows.

### Agent Lab

- Keep Agent Lab bounded, visible, and reversible.
- Preserve proposal/review/read-only workflows before any write automation.
- Add archived session visibility controls.

### Workstation

- Add optional non-NVIDIA GPU detection where practical.
- Keep GPU tuning controls out of scope until explicitly reviewed.
- Keep monitoring read-only by default.
