---
suite: hermes-v1
category: config
risk: high
purpose: Test agent-style Docker Compose review and safe patch planning.
scoring_focus:
  - risk identification
  - safe correction
  - no broad rewrites
  - no unsafe mounts
---

# Docker Compose Agent Review

Review this service:

    services:
      agent-worker:
        image: example/agent-worker:latest
        container_name: agent-worker
        privileged: true
        volumes:
          - /:/host
          - /var/run/docker.sock:/var/run/docker.sock
          - ~/.ssh:/root/.ssh
        environment:
          - DEBUG=true
        restart: always

Task:
- Identify the highest-risk issues.
- Explain why they matter.
- Provide a safer revised service.
- Do not remove every capability unless justified.
- Keep the answer concise and patch-oriented.
