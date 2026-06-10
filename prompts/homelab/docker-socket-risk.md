# Test: Docker socket mount risk

## Category

homelab

## Prompt

Review this Docker Compose service for safety.

```yaml
services:
  helper:
    image: example/helper:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /:/host
    restart: unless-stopped
```

Explain the risks and propose a safer alternative. Assume this is for a home Ubuntu Docker server.
