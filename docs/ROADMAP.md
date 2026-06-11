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

## Next milestone

### alpha v0.11.7 — public-alpha generic install audit

Goal: make the repository more obviously usable by someone other than the original author on a different Linux machine.

Planned work:

- Remove remaining machine-shaped examples from bundled prompts.
- Clean stale documentation and roadmap wording.
- Align troubleshooting and install instructions.
- Review default config paths for generic public use.
- Run a clean-clone install test.
- Decide whether to keep source-available/no-license posture or add an explicit open-source license.

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

### Local Eval / Quant Lab

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
