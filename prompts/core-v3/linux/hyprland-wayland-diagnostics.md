---
suite: core-v3
category: linux
risk: medium
purpose: Test Wayland/Hyprland troubleshooting quality without stale Sway assumptions.
scoring_focus:
  - practical diagnostics
  - no stale Sway assumptions
  - NVIDIA/Wayland awareness
  - non-destructive troubleshooting
---

# Hyprland / Wayland Diagnostics

A user on Arch Linux with Hyprland and an NVIDIA GPU reports:

"After an update, some apps launch with weird scaling, screen sharing is inconsistent, and one Electron app flickers."

Task:
Give a conservative diagnostic plan.

Requirements:
- Do not assume Sway.
- Include Wayland/XWayland distinction.
- Include NVIDIA-specific checks.
- Include portal/screen-sharing checks.
- Avoid destructive changes.
- Give commands only where useful.
- Keep it ordered from least risky to more invasive.
