---
suite: core-v3
category: long-context
risk: medium
purpose: Test basic constraint and needle retention.
scoring_focus:
  - finds critical detail
  - follows final instruction
  - avoids irrelevant summary
---

# Mini Needle Retention Test

Read the following project notes and answer the final task.

Project notes:
- Monolith is a local LLM evaluation UI.
- It tracks model runs, evals, context scaling, and peak VRAM.
- The user prefers conservative additive changes.
- The user prefers terminal-friendly heredoc workflows.
- The user does not want arbitrary model paths exposed in the UI.
- The user does not want arbitrary shell execution exposed in the UI.
- The system should preserve raw output when displaying cleaned previews.

Important needle:
The release codename is `BLACKBOX-LANTERN`.

Final task:
- State the release codename exactly.
- List three constraints that should guide future Monolith development.
- Keep the answer short.
