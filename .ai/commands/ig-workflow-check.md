# Command: ig-workflow-check

## Purpose

Fast **pre-PR** checklist for scraper changes.

## When to use

Before pushing parser, selector, or Thor-related work.

## Flow

1. `python3 -m pytest src/igscraper/tests/test_load_schema.py src/igscraper/tests/test_flatten_schema_contract.py src/igscraper/tests/test_parser_golden_contract.py src/igscraper/tests/test_thor_worker_id.py -q`
2. If you touched selectors: local headed run on **one** known profile/post URL.
3. If you touched `[trace]` or enqueue: re-read [docs/contracts/thor-handshake.md](../../docs/contracts/thor-handshake.md).
4. Confirm `HANDOFF.md` has the next task if you are mid-stream.
5. If a step is skipped, mark it explicitly as `SKIP` with honest reason (env/time/account wall) and impact.

## Output format

- commands + pass/fail  
- manual check yes/no  
- skipped checks (if any) + reason + risk  

## Done signal

Proof attached (log snippet or “N/A” with reason).

## Guardrails

- Do not skip Postgres preflight failures by commenting out `cli.py` checks in a drive-by.
