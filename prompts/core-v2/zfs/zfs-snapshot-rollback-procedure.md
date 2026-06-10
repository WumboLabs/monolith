# ZFS Snapshot / Rollback Procedure

A user has a ZFS pool with datasets used for homelab storage. They want a safe procedure for taking a snapshot before risky changes and rolling back if needed.

Task:

Write a conservative ZFS snapshot and rollback procedure.

Requirements:

- Include commands to list pools and datasets.
- Include creating a named snapshot.
- Include verifying the snapshot exists.
- Explain rollback risks.
- Warn about destroying newer changes after rollback.
- Include safer alternatives like cloning or copying data out first.
- Include verification after rollback.
- Avoid destructive commands unless clearly labeled.
