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

## Dependency and runtime strategy

Monolith should move toward a more self-contained local application, but in conservative stages.

Near-term principle:

- detect dependencies before trying to manage them
- explain missing dependencies clearly
- keep system-level changes explicit
- avoid automatic GPU driver, CUDA, package-manager, firewall, or kernel-module changes in early alpha

### alpha v0.11.14 — dependency and runtime detection

Goal: expand setup diagnostics so Monolith can clearly report local runtime readiness.

Planned work:

- Detect Python environment quality.
- Detect whether `nvidia-smi` is available.
- Detect visible NVIDIA GPU state when available.
- Detect llama.cpp binaries.
- Detect whether llama.cpp binaries support required commands.
- Detect configured GGUF inventory roots.
- Detect missing model/profile/runtime prerequisites.
- Show dependency/runtime status in `/setup`.
- Keep missing GPU/model/runtime items as warnings unless they block core app startup.

### alpha v0.11.15 — llama.cpp runtime manager design

Goal: design a safe runtime registry for user-provided and Monolith-managed llama.cpp binaries.

Planned work:

- Define runtime metadata format.
- Track llama.cpp commit/build/version metadata.
- Track runtime path, backend type, and supported commands.
- Track checksum/build provenance for managed runtimes.
- Support user-provided runtime paths.
- Support future Monolith-managed runtime bundles without changing existing configs.

### alpha v0.11.16 — optional managed llama.cpp runtime prototype

Goal: prototype optional managed llama.cpp runtime support without bundling binaries directly into the main repo.

Planned work:

- Prototype managed CPU runtime registration.
- Prototype managed CUDA runtime registration if technically safe.
- Store managed runtimes outside committed source.
- Prefer GitHub release artifacts or a separate runtime distribution location.
- Add runtime smoke tests.
- Keep system GPU driver installation out of scope.

Later packaging candidates:

- packaged CLI
- `pipx install monolith`
- `monolith init`
- `monolith doctor`
- `monolith web`
- optional release-artifact runtime bundles
- desktop/app packaging exploration

Out of scope for early alpha:

- automatic NVIDIA driver installation
- automatic CUDA toolkit installation
- system package manager mutation
- kernel module changes
- secure boot handling
- firewall changes
- background system service installation without explicit review


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
