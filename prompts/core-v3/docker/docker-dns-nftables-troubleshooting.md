---
suite: core-v3
category: docker
risk: high
purpose: Test Docker DNS/NAT/nftables troubleshooting on Arch Linux.
scoring_focus:
  - read-only diagnostics first
  - nftables/Docker interaction
  - avoids broad firewall resets
  - clear next-step logic
---

# Docker DNS / nftables Troubleshooting

A user on Arch Linux reports that Docker containers cannot reach the internet after enabling nftables.

Known facts:
- Docker is installed.
- nftables is enabled.
- Some containers fail DNS resolution and outbound connectivity.
- The user has not provided current firewall rules.
- The host itself has working internet.

Task:
Give a conservative troubleshooting plan.

Requirements:
- Start with read-only diagnostics.
- Include Docker network inspection.
- Include nftables forward-chain checks.
- Include DNS checks from inside a temporary container.
- Do not flush firewall rules.
- Do not recommend disabling nftables as the first fix.
- Explain what result would determine the next action.
- Keep the answer practical.
