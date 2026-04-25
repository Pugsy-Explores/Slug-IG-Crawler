# Command: ig-capture-strategy-session

## Purpose

After an IG Scraper strategy chat, convert decisions into durable repo memory so the next session can execute immediately.

Use after architecture discussions, parser redesign decisions, selector recovery plans, Thor integration decisions, release planning, or feature sequencing.

## Flow

1. Read:
   - `.ai/memory/CURRENT_STATE.md`
   - `.ai/memory/HANDOFF.md`
2. Extract from the strategy session:
   - Durable decisions
   - Temporary priorities (next 1-5 tasks)
   - Rejected options (short bullets)
   - Open questions
   - Risks / assumptions
3. Update `CURRENT_STATE.md` (source of truth):
   - active queue
   - selector drift hotspots
   - parser debt
   - Thor blockers
   - release priorities
   - approved next tasks
4. Update `HANDOFF.md` (short):
   - what changed
   - exact next task
   - blockers
   - resume pointer (file / command / test)
5. If facts changed, recommend `ig-sync-docs` (do not silently rewrite docs when code truth did not change).

## Output

- updated files:
  - `CURRENT_STATE.md`
  - `HANDOFF.md`
- summary:
  - 3 durable decisions
  - next immediate task
  - docs sync needed: yes/no

## Done signal

A fresh GPT or Cursor session can execute without rereading the strategy chat.

## Guardrails

- No new memory files.
- No transcript dumping.
- `CURRENT_STATE` owns priorities.
- `HANDOFF` stays short.
- If uncertain, log as risk (not fact).
- Docs reflect implementation truth only.
