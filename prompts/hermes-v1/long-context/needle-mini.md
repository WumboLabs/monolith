---
suite: hermes-v1
category: long-context
risk: medium
purpose: Test basic needle retention for Hermes backend candidates.
scoring_focus:
  - finds critical detail
  - follows final instruction
  - avoids irrelevant summary
---

# Hermes Mini Needle Test

Context:
- The model is being tested as a possible Hermes Agent backend.
- Hermes requires large context handling.
- The model should avoid inventing tools or command output.
- The model should preserve user constraints over long conversations.
- The model should prefer verification before mutation.

Important needle:
The Hermes viability phrase is `GREEN-THREAD-64K`.

Final task:
- State the Hermes viability phrase exactly.
- List two safety behaviors required of an agent backend.
- Keep the answer short.
