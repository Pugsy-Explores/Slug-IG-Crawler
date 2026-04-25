# Command: ig-plan-task

## Purpose

Produce an **execution-grade plan** before meaningful scraper work (DOM, capture path, parser, session, Thor integration).

## When to use

Any non-trivial change: new workflow step, selector updates, `flatten_schema.yaml`, pipeline mode behavior, Postgres preflight, or Thor config contract.

## Flow

1. Read `.ai/memory/HANDOFF.md`, `.ai/memory/CURRENT_STATE.md`, then `.ai/BOOT_CONTEXT.md`.
2. Skim [README.md](../../README.md) mode table and [docs/architecture.md](../../docs/architecture.md) if touching flow.
3. If parser/GQL: read [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md) and `flatten_schema.yaml` relevant section.
4. Classify: selector / parser / session / workflow / integration / test-only.
5. State **ownership layer** and **explicit non-goals** (especially: no `utils.py` mega-refactor in this PR).
6. Define **partial_success** and **retryable** behavior for the slice if user-visible.
7. Add a quick **blast radius** check: what can break (selector/parser/session/Thor trace), who consumes it, and the smallest rollback.
8. List validation: `pytest` paths, local browser check, or `ig-compatibility-check` for Thor.

## Output format

- objective  
- layer  
- scope in / out  
- risks (IG drift, cookie, CDP)  
- files likely touched  
- tests / commands  
- done when  
- rollback  

## Done signal

Another engineer can execute without spelunking `utils.py` blindly.

## Guardrails

- Do not plan “rewrite utils” as a side quest.  
- If Thor-related, cite `docs/contracts/thor-handshake.md` once it exists.
