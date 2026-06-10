# Docker Compose Review

Review this Docker Compose snippet for reliability and safety issues:

```yaml
services:
  app:
    image: example/app:latest
    container_name: app
    network_mode: host
    volumes:
      - /:/host
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - API_KEY=super-secret-value
    restart: always
```

Task:

Identify risks and recommend safer alternatives.

Requirements:

- Be specific.
- Explain why each issue matters.
- Suggest conservative fixes.
- Do not overcomplicate the setup.
- Do not claim the app is malicious.
- Focus on operational safety.
