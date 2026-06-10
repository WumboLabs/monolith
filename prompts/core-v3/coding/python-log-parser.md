---
suite: core-v3
category: coding
risk: medium
purpose: Test practical Python scripting.
scoring_focus:
  - correctness
  - edge cases
  - simple design
  - runnable code
---

# Python Log Parser

Write a Python script that reads a log file and prints a summary of error lines.

Input:
- A path to a log file is passed as the first command-line argument.
- Lines may contain levels such as INFO, WARN, ERROR, CRITICAL.
- Some lines may not contain a level.

Task:
Write a script that:
- Counts total lines.
- Counts ERROR and CRITICAL lines.
- Prints the first 10 ERROR or CRITICAL lines with line numbers.
- Handles a missing file gracefully.
- Uses only the Python standard library.

Return:
- The complete script.
- A brief note on how to run it.
