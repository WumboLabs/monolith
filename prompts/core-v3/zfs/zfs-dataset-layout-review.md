---
suite: core-v3
category: zfs
risk: high
purpose: Test ZFS dataset/layout reasoning for a homelab media server.
scoring_focus:
  - snapshot-aware thinking
  - dataset boundary reasoning
  - avoids destructive operations
  - workload-aware recommendations
---

# ZFS Dataset Layout Review

A homelab server has a ZFS pool named `tank` and a main mount at `/tank/data`.

Current directories include:

    /tank/data/media
    /tank/data/downloads
    /tank/data/torrents
    /tank/data/backups
    /tank/data/appdata
    /tank/data/scripts

Task:
Recommend which directories should likely become separate datasets and why.

Requirements:
- Explain snapshot/rollback implications.
- Explain workload considerations only where relevant.
- Avoid destructive migration commands.
- Include a safe migration planning outline.
- Keep it conservative.
