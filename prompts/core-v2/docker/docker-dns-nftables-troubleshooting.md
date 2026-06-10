# Docker DNS / nftables Troubleshooting

A Linux workstation runs Docker containers. Containers suddenly cannot resolve DNS or reach the internet.

Known context:

- Docker is installed and running.
- nftables is enabled.
- The firewall forward policy may be dropping forwarded container traffic.
- Docker NAT rules may need to be restored after firewall changes.

Task:

Give a conservative troubleshooting procedure.

Requirements:

- Start with non-destructive checks.
- Include commands to inspect Docker networks, container DNS, nftables rules, and forwarding.
- Explain why nftables forward policy can break Docker.
- Include safe fixes.
- Include verification commands.
- Include rollback notes.
- Do not recommend disabling the firewall permanently.
