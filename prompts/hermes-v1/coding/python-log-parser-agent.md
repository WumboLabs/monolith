---
suite: hermes-v1
category: coding
risk: medium
purpose: Test coding competence in an agent-useful style.
scoring_focus:
  - runnable code
  - concise explanation
  - edge cases
  - no overengineering
---

# Python Log Parser Agent Test

Write a Python script that reads a log file and prints a compact summary.

Requirements:
- Accept log path as first CLI argument.
- Count total lines.
- Count WARNING, ERROR, and CRITICAL lines.
- Print first 10 ERROR or CRITICAL lines with line numbers.
- Handle missing files gracefully.
- Use only the standard library.
- Keep the explanation short.

Return:
- Complete script.
- One short test command.
