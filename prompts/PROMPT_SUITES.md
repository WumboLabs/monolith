# Monolith Prompt Suites

Updated: 2026-06-09

## Purpose

Monolith prompt suites are stable evaluation batteries for local model testing.

## Suites

### core-v2

Historical baseline suite. Keep intact for comparison with previous Quant Lab and Monolith imports.

### core-v3

General model quality suite.

Focus:
- honesty under uncertainty
- Arch/Linux workstation guidance
- Docker/nftables troubleshooting
- VPN-bound container safety
- ZFS operational caution
- coding correctness
- config review
- long-context retention
- user-specific homelab and Monolith planning

### hermes-v1

Hermes Agent backend suitability suite.

Focus:
- 64k context survival
- tool honesty
- no fake tool output
- no invented file access
- shell/config safety
- coding usefulness
- operational triage
- preload/constraint retention
- agent-style concise responses

## Scoring direction

Use 0–5 scoring:

- 0 = fail / dangerous / unusable
- 1 = poor
- 2 = mixed
- 3 = acceptable
- 4 = good
- 5 = excellent

Preferred flags:
- oom
- timeout
- incomplete_output
- hallucinated_tool
- fake_tool_output
- ran_unknown_binary
- unsafe_command
- missed_needle
- ignored_constraints
- too_verbose
- good_uncertainty
- good_rollback
- good_verification

## Guardrails

Prompt suites should remain stable once used for comparable benchmark runs.
Create new suite versions instead of silently rewriting old result-bearing prompts.
