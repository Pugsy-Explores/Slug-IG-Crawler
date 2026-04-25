# Command: ig-triage-failure

## Purpose

Fast-route a failed run to the right IG command without guesswork.

## When to use

Run failed and root cause is unclear.

## Flow

1. Capture first concrete failure signal (error line, log snippet, or failing test).
2. Classify into one lane:
   - `session` (login/checkpoint/cookies/account context)
   - `selector` (missing elements/modal/grid/comment DOM)
   - `parser` (schema/flatten/golden mismatch)
   - `infra` (DB/preflight/compose/env/runtime wiring)
   - `contract` (`[trace]`, Thor handshake, payload shape)
3. Route immediately:
   - `session` -> `ig-session-debug`
   - `selector` -> `ig-selector-audit`
   - `parser` -> `ig-workflow-check`
   - `infra` -> `ig-compatibility-check`
   - `contract` -> `ig-plan-task` then `ig-sync-docs` if behavior changed
4. If blocked >45m, shrink scope to one failing seam or park with reason + resume trigger in `HANDOFF`.

## Output format

- failure signal
- lane picked
- routed command
- first next action

## Done signal

One lane chosen and one next command started.

## Guardrails

- Pick one primary lane; do not run all debug commands in parallel.
- Do not patch code before lane selection unless the fix is trivial and proven.
