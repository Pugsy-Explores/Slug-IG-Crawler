# Command: ig-compatibility-check

## Purpose

Verify **Thor + Postgres preflight** alignment before blaming “IG broke”.

## When to use

Before a release, after Thor env changes, or when runs exit early with DB/schema errors.

## Flow

0. Read `CURRENT_STATE.md` first; it owns live priorities and blocker context.
1. Read `docs/contracts/thor-handshake.md` when present; else [README.md](../../README.md) Thor section and [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md) § Postgres.
2. Confirm compose / env: Postgres reachable, `DATABASE_URL` or equivalent matches Thor worker expectations.
3. Confirm **preflight tables** exist (repo SQL under `sql/` / migrations — use what README documents).
4. Confirm **`[trace].thor_worker_id`** is set when running under Thor (see `test_thor_worker_id.py` and pipeline trace wiring).
5. Run fast local checks:
   ```bash
   cd /path/to/ig_profile_scraper && python -m pytest src/igscraper/tests/test_thor_worker_id.py src/igscraper/tests/test_load_schema.py -q
   ```

## Output format

- preflight: pass / fail + which table or env  
- trace field: present / missing in config  
- recommendation  

## Done signal

You know whether the failure is **infrastructure** or **extraction**.

## Guardrails

- Do not paste production URLs or credentials into chat or commits.
- If blocked >45m: shrink scope to a single failing seam, run focused audit evidence, or park with reason + resume trigger in `HANDOFF`.
- If contract or parser behavior changed while fixing, run `ig-sync-docs`.
