# Slug-Ig-Crawler — BOOT_CONTEXT

**Package:** `igscraper` (PyPI `slug-ig-crawler`)  
**Read order:** `HANDOFF.md` → `CURRENT_STATE.md` → this file → [README.md](../README.md) → [docs/architecture.md](../docs/architecture.md).

## What this repo is

A **hybrid browser extraction engine**: Selenium + Chrome (+ CDP/network capture), TOML/Pydantic config, CLI-driven **workflows** that persist to **Postgres** (and optionally GCS). Not a pure HTTP API client. **Anti-breakage** work is normal operations (DOM + internal GraphQL key drift).

## Ownership layers (do not blur)

Canonical map (same content, maintained in one place for deep links): [docs/architecture/ownership-boundaries.md](../docs/architecture/ownership-boundaries.md).

| Layer | Owns | Primary code |
|-------|------|----------------|
| **Workflow** | Mode selection, batching, pipeline orchestration | `pipeline.py`, mode rules in [README.md](../README.md) |
| **Browser automation** | Driver lifecycle, CDP, tabs, scrolling | `backends/selenium_backend.py`, `chrome.py`, `pages/` |
| **Request / capture** | Network log, GraphQL response bodies | `utils.py` (capture), backend hooks |
| **Extraction / parser** | DOM reads, flatten rules, Pydantic models | `utils.py`, `pages/`, `models/`, `registry_parser.py`, `flatten_schema.yaml` |
| **Session / cookie** | Login, cookie JSON, Chrome/Driver pairing | `login_Save_cookie.py`, `paths.py`, `bootstrap.py` |
| **Output / storage** | DB rows, GCS paths, enqueue | `services/`, SQL scripts |
| **Integration** | `PUGSY_PG_*`, Thor `[trace].thor_worker_id`, Docker | `cli.py` (`_preflight_postgres_ready`), `pipeline.py` |
| **Release / reliability** | CI, versioning | `.github/workflows/`, `pyproject.toml` |

## Mode truth (Pipeline)

1. `[data].urls_filepath` **exists** → URL-file mode (overwrites `[main].mode`).  
2. Else non-empty `target_profiles` → profile mode.  
3. Else warning, no scrape.

## Thor / Postgres preflight

Before `Pipeline`, `run` checks DB reachable and `public.crawled_posts`, `public.crawled_comments` exist (`cli.py`). **Thor containers** must pass the same DB into the scraper process/network as the host — see `ig-compatibility-check` and [docs/contracts/thor-handshake.md](../docs/contracts/thor-handshake.md).

## Fragility source of truth

[audit-output-igscraper/executive_summary.md](../audit-output-igscraper/executive_summary.md) — DOM selectors, `xdt_*` keys, CDP, comments path.

## Vocabulary (shared with contracts)

Machine-readable field meanings (`status`, `error_code`, `trace_id`, …): [docs/contracts/shared-vocabulary.md](../docs/contracts/shared-vocabulary.md). Repo-local usage: [docs/contracts/scrape-run-contract.md](../docs/contracts/scrape-run-contract.md).

- **status** — run/progress state in logs/DB context (not Thor job states).  
- **terminal** — run exited (success or `SystemExit`); no partial continuation unless explicitly designed.  
- **partial_success** — some posts/comments written, some skipped/failed; document per workflow.  
- **retryable** — safe to re-run (idempotent enough); cookie/login failures often **not** retryable without human/session fix.  
- **freshness** — data age vs scrape time; product concern downstream.  
- **error_code** — prefer stable exit messages from CLI/preflight; avoid ad-hoc strings in new code.

## Memory rule

Only `.ai/memory/CURRENT_STATE.md` and `HANDOFF.md`. No extra memory files unless operational pain forces it.
