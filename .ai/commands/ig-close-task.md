# Command: ig-close-task

## Purpose

Close a session with **durable** handoff and accurate memory.

## When to use

When a slice is proven or intentionally parked.

## Flow

1. Confirm proof (test name, log snippet, or “parked: reason”).
2. Update `CURRENT_STATE.md` (**source of truth for priorities**): priorities, parser/drift notes, Thor blockers.
3. Update `HANDOFF.md`: completed (short bullets), **exact next task** (one line), blockers, resume pointer.
4. If blocked >45m and no proof path, mark one: **shrink scope**, **run compatibility/audit check**, or **park with reason + resume trigger**.
5. If contracts, parser behavior, or `flatten_schema` changed, note and run `ig-sync-docs`.

## Output format

- memory updated (yes/no)  
- what changed in one paragraph  

## Done signal

Resume in under two minutes from `HANDOFF` alone.

## Guardrails

- Do not duplicate git history in prose.
- **Closed vs parked:** closed = proof shipped; parked = explicitly paused with reason + next trigger in `HANDOFF`.
