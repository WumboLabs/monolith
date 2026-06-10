---
suite: core-v3
category: long-context
risk: medium
purpose: Test whether a model preserves constraints across a longer project brief.
scoring_focus:
  - instruction retention
  - no forbidden recommendations
  - prioritization
---

# Constraint Retention Test

A user is developing a local LLM evaluation tool named Monolith.

Constraints:
- Conservative additive changes only.
- No arbitrary shell execution from the UI.
- No arbitrary model paths from the UI.
- Active model profiles only.
- Approved prompt roots only.
- Preserve raw output.
- Prefer checkpointing after working milestones.
- Prefer terminal commands using heredoc-style file replacement.
- Avoid full rewrites unless explicitly requested.

The user asks:
"Give me the next implementation plan."

Task:
Provide the next three implementation milestones.

Requirements:
- Respect all constraints.
- Do not suggest a full rewrite.
- Do not suggest exposing arbitrary shell commands.
- Include verification and checkpointing.
- Keep the response concise.
