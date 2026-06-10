# Command Proposal Prompt

Draft a command proposal only. Do not claim to run it.

Every command proposal must include:

Title:
Purpose:
Command:
Expected effect:
Risk level:
Files affected:
Rollback plan:
Verification step:
Requires approval: yes

Rules:
- Prefer read-only commands first.
- Avoid destructive commands.
- Avoid sudo.
- Avoid package managers.
- Avoid network installers.
- Avoid Docker socket access.
- Avoid credential paths.
- Do not chain unrelated commands.
