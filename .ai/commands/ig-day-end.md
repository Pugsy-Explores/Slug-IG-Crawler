# Command: ig-day-end

## Purpose

V1 **script-backed** daily closeout: prompts for what shipped today, updates `.ai/memory/`, and appends `WORK_LOG.md`. This **does not replace** `ig-close-task` or `ig-sync-docs`; it is convenience automation only.

## When to use

End of a work block when you want durable memory + a dated log without hand-editing three files.

## Flow

1. From repo root:

   ```bash
   python scripts/day_end.py
   ```

2. Answer prompts (finish each multi-line block with a line containing only `.`):

   - Completed work today
   - Proof / tests run
   - Next task (one line)
   - Blockers (optional: `.` alone for none)
   - Resume pointer (file / command / location)

3. Optional:

   ```bash
   python scripts/day_end.py --dry-run
   ```

   Prints what would be written; **no file writes**; subprocess checks are skipped.

4. Optional checks (step 1 of `ig-workflow-check`):

   ```bash
   python scripts/day_end.py --run-checks
   ```

   Runs the contract/pytest slice from `.ai/commands/ig-workflow-check.md`. Non-zero exit skips memory writes. Manual steps in that command still apply when relevant.

## Files touched

- `.ai/memory/CURRENT_STATE.md` — `**Last touched:**` timestamp; `## Day-end snapshot` (created or replaced)
- `.ai/memory/HANDOFF.md` — done, proof, next, blockers, resume sections; session date
- `WORK_LOG.md` — append dated entry (created if missing)

## Guardrails

- Stdlib-only script; no markdown parser; sections matched by known `##` headings only.
- If a required heading is missing from `HANDOFF.md`, the script exits with an error (fix template first).
- `--dry-run` never writes files and never runs subprocess checks.

## Done signal

Script prints `Done: CURRENT_STATE.md, HANDOFF.md, WORK_LOG.md updated.`
