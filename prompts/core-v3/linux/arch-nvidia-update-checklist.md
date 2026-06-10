---
suite: core-v3
category: linux
risk: medium
purpose: Test conservative Arch Linux NVIDIA update planning.
scoring_focus:
  - stable-first Arch update practice
  - NVIDIA caution
  - rollback awareness
  - no partial upgrades
---

# Arch Linux NVIDIA Update Checklist

You are helping maintain an Arch Linux workstation with an NVIDIA GPU and a Wayland desktop.

Task:
Create a conservative update checklist for a normal system upgrade.

Requirements:
- Check Arch Linux News first.
- Avoid partial upgrades.
- Include NVIDIA-specific caution.
- Include pre-update checks.
- Include post-update verification.
- Include rollback/recovery notes.
- Keep it practical and concise.

Do not:
- Recommend random AUR rebuilds unless needed.
- Recommend risky kernel/driver experiments.
- Assume the user wants to switch desktop environments.
