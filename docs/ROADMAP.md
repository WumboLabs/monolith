# Roadmap

## Near future

### WumboCore UI theme pass

Apply the WumboCore / Monochrome Lime visual system consistently across Monolith.

This is intentionally separate from the alpha v0.11.4 public-readiness patch.

#### Palette

| Role | Hex |
|---|---|
| Background | `#0D0F14` |
| Near-black panel | `#101216` |
| Elevated panel | `#171A21` |
| Border | `#2A2F38` |
| Cool gray | `#9AA3AC` |
| Primary text | `#F2F2F2` |
| Body text | `#C9CED6` |
| Muted text | `#8E96A3` |
| Lime accent | `#C6FF33` |
| Warning | `#E6D26A` |
| Error | `#F26D6D` |

#### Design direction

- dark technical monochrome base
- restrained lime accent
- readable daily-driver UI
- terminal/workbench feel
- strong contrast without neon overload
- consistent cards, tables, buttons, forms, status pills, and detail pages

#### Scope

- global CSS variables
- dashboard cards
- Chat
- Models
- Eval
- Agent Lab
- Context
- Workstation
- local/download detail pages
- tables
- forms
- buttons
- status pills
- logs and code blocks

#### Non-goals for the theme pass

- no behavior changes
- no model workflow changes
- no downloader logic changes
- no database schema changes unless needed for UI state later

Goal: make Monolith visually consistent with the WumboCore palette without destabilizing alpha functionality.
