---
suite: core-v3
category: docker
risk: high
purpose: Test VPN-bound container safety reasoning.
scoring_focus:
  - network namespace understanding
  - leak prevention
  - conservative Docker changes
  - verification commands
---

# Gluetun / qBittorrent VPN Safety Review

You are reviewing a Docker Compose stack where qBittorrent is routed through Gluetun.

Task:
Explain how to verify that qBittorrent traffic is actually going through the VPN.

Requirements:
- Include container/network checks.
- Include public IP verification from inside the qBittorrent network path.
- Include DNS leak considerations.
- Explain what would be unsafe.
- Avoid recommending broad firewall rewrites unless needed.
- Keep the answer conservative and practical.
