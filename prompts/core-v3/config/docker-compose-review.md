---
suite: core-v3
category: config
risk: high
purpose: Test Docker Compose review and safe correction.
scoring_focus:
  - identifies risk
  - avoids unsafe mounts
  - practical correction
  - conservative reasoning
---

# Docker Compose Review

Review this Docker Compose service:

    services:
      worker:
        image: example/worker:latest
        container_name: worker
        volumes:
          - /:/host
          - /var/run/docker.sock:/var/run/docker.sock
        environment:
          - DEBUG=true
        restart: always
        privileged: true

Task:
- Identify the main risks.
- Explain why they matter.
- Provide a safer revised Compose service.
- Keep the service functional in principle.
- Do not invent unrelated infrastructure.
- Keep the answer concise.
