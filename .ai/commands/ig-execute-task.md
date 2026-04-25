# Command: ig-execute-task

## Purpose

Turn an approved **ig-plan-task** (or a one-line `HANDOFF` slice) into **shipped proof**.

## When to use

After scope is fixed; not for vague exploration.

## Flow

1. Read `HANDOFF.md` + `CURRENT_STATE.md` (`CURRENT_STATE` owns priorities).
2. Pick **one** slice. If unclear, run `ig-plan-task` first.
3. Define **proof**: passing test, CLI behavior, or documented repro + fix.
4. Implement; stay in the **correct layer** (no orchestrator logic in page objects, etc.).
5. Run **minimal** tests (targeted `pytest`, not full suite unless needed).
6. If blocked >45m: **shrink scope**, run `ig-compatibility-check`/targeted audit, or **park** with reason + resume trigger.
7. If contract/parser/`flatten_schema` behavior changed, run `ig-sync-docs`.
8. Update `HANDOFF.md` with exact next step.

## Output format

- slice  
- proof  
- commands run + result  
- next step (one line)  

## Done signal

Proof exists; `HANDOFF` updated.

## Guardrails

- **Forbidden:** same PR as large `utils.py` refactor + feature (see `execution-master` prompt).  
- Do not weaken Postgres preflight without an explicit contract change.
