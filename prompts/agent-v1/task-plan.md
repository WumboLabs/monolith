# Task Plan Prompt

Given the user's goal and provided context, create a conservative task plan.

Requirements:
- Keep the plan bounded.
- Prefer read-only inspection before changes.
- Do not propose execution as already completed.
- Identify missing context.
- Identify risks.
- Include verification steps.
- Include rollback or recovery notes where relevant.

Return a structured plan suitable for saving in Monolith Agent Lab.
