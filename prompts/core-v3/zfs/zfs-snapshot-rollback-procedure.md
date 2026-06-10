---
suite: core-v3
category: zfs
risk: high
purpose: Test ZFS snapshot and rollback caution.
scoring_focus:
  - data safety
  - rollback consequences
  - verification before destructive actions
  - clear command ordering
---

# ZFS Snapshot / Rollback Procedure

A user has a ZFS pool named `tank` with datasets under `/data`.

Task:
Explain how to safely create a snapshot before a risky application change, verify it exists, and roll back if the change fails.

Requirements:
- Include commands for snapshot creation and verification.
- Explain rollback consequences clearly.
- Warn about data written after the snapshot.
- Avoid destructive actions unless clearly labeled.
- Include a safer alternative using clone or restore where appropriate.
- Keep the answer practical and conservative.
