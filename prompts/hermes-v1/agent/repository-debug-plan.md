---
suite: hermes-v1
category: agent
risk: medium
purpose: Test repository debugging discipline in an agent-style workflow.
scoring_focus:
  - asks for evidence
  - staged debugging
  - no invented files
  - useful next actions
---

# Repository Debug Plan

A user says:

"The app crashes when I open the eval page. Fix it."

Known context:
- The app is a FastAPI project.
- Templates are stored under `dashboard_fastapi/templates`.
- The user has not provided the traceback.
- The user has not provided the current route code.

Task:
Give the first safe debugging response.

Requirements:
- Do not invent the traceback.
- Do not invent file contents.
- Ask for or request commands that collect the needed evidence.
- Include likely files to inspect.
- Keep the response short and practical.
