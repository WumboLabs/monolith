# Monolith UI Workbench Concept

Monolith's interface should feel like a local technical workbench, not a generic SaaS dashboard.

The target is a web UI that visually aligns with future CLI/TUI workflows while staying practical in the browser.

## Design direction

Use a terminal/workbench layout language:

- persistent shell
- left navigation rail
- top system/status strip
- dense but readable panels
- small technical labels
- visible state and guardrails
- monospace detail surfaces
- sharp bordered cards
- restrained lime accents
- dark-mode-first WumboCore palette

## Current baseline

The current app already has:

- sidebar navigation
- collapsible shell
- top workstation ticker
- WumboCore / Monochrome Lime palette
- cards, panels, status pills, tables, and run alerts
- setup diagnostics and first-run empty states

The next UI pass should refine these into a coherent workbench shell rather than replacing the app.

## Visual grammar

Use consistent workbench primitives.

### Shell

The shell should expose:

- app identity
- current version
- primary navigation
- system status
- active workspace

The shell should feel persistent across pages.

### Panels

Panels should look like terminal/workbench panes:

- thin borders
- low-radius or square corners
- clear section headers
- compact metadata rows
- minimal glow
- no glossy gradients
- no neon overload

### Status

Status should be explicit and scannable:

- OK
- WARN
- ERROR
- RUNNING
- QUEUED
- READ-ONLY
- EXPERIMENTAL
- CONTROLLED

Warnings and errors should tell the user what to do next.

### Tables

Tables should be dense but not cramped:

- strong column labels
- subtle row striping
- compact status pills
- monospace paths and IDs
- readable overflow behavior

### Accent usage

The lime accent is an instrument light, not the dominant color.

Use it for:

- active nav state
- focused controls
- selected/active states
- small status accents
- terminal-like cursors or indicators

Avoid:

- large neon blocks
- heavy green backgrounds
- cyberpunk glow
- glossy AI startup styling

## v0.11.9 implementation scope

The first implementation should be conservative and additive.

### In scope

- add a final CSS override layer for the workbench shell
- refine global shell spacing and panel styling
- improve dashboard landing page hierarchy
- improve setup/models/chat/eval page consistency
- keep existing routes and APIs unchanged
- keep existing class names where possible

### Out of scope

- deep page rewrites
- new frontend framework
- arbitrary command execution
- model workflow changes
- clean-clone install test
- CLI/TUI implementation
- Agent Gateway implementation

## Intended milestone outcome

By the end of alpha v0.11.9, Monolith should still work the same, but feel more like:

- a local instrument panel
- a model lab console
- a terminal-friendly workbench
- a future TUI-compatible control surface

The clean-clone install test should happen after this UI shell stabilizes so tester notes match the interface users will see.

## v0.11.9 result

The v0.11.9 UI shell establishes a cohesive terminal-workbench baseline for Monolith:

- consistent dark workbench styling using the WumboCore palette
- fixed local WebUI launcher on `http://127.0.0.1:8765/`
- shared table pagination with compact 5-row defaults
- active tab highlighting
- more terminal-readable typography

This is not the final multi-pane/TUI design. Deeper pane behavior, command-bar affordances, docked inspectors, and CLI/TUI workflows remain future polish work.
