# Python Log Parser

Write a dependency-free Python 3 script that parses a log file and summarizes errors.

Input:

- A path to a text log file.
- Lines may contain timestamps, INFO, WARNING, ERROR, or arbitrary text.

Requirements:

- Use only the Python standard library.
- Accept the log path as a command-line argument.
- Count total lines.
- Count lines containing ERROR, WARNING, and INFO.
- Print the first 10 ERROR lines.
- Handle missing files cleanly.
- Handle Unicode decode errors safely.
- Include clear, runnable code.
