# Command: ig-sync-docs

## Purpose

After changing **contracts**, **architecture**, or **parser/schema** behavior, ensure **canonical docs** stay aligned without duplicating README prose.

## When to use

`flatten_schema.yaml` edits, new `docs/contracts/*`, ownership moves, or new golden fixtures.

## Flow

0. No-op gate: if no contract/parser/architecture behavior changed, stop and record “docs sync: not needed”.
1. Update the **contract** or **architecture** file under `docs/` first (source of truth for that topic).
2. If README table-of-contents or mode behavior changed, update [README.md](../../README.md) **only** with pointers (no long copies).
3. Bump `.ai/memory/CURRENT_STATE.md` with a one-line “docs drift” note if reviewers need to know.
4. Run `ig-workflow-check` before opening a PR.

## Output format

- files touched  
- what readers should re-read  

## Done signal

No contradictory statements between `docs/contracts/` and code comments you added.

## Guardrails

- Do not paste secrets or live IG captures into `docs/`.
