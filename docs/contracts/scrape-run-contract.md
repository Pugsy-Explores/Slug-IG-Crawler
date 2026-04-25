**Cross-repo vocabulary:** [shared-vocabulary.md](shared-vocabulary.md).


**Structured timing logs:** JSON lines from the pipeline/backend include an additive **`envelope`** (`igscraper-log-v1`) with shared `status` / `error_code` / `trace_id` — see [shared-vocabulary.md](shared-vocabulary.md) Phase 2.

# Contract: scrape run (CLI → pipeline)

**Canonical narrative:** [README.md](../../README.md) (modes, TOML), [docs/architecture.md](../architecture.md) (components). This file captures **operational contracts** only.

## Inputs

- **Config:** TOML resolved by `Slug-Ig-Crawler` (`--config` or default `~/.slug/config.toml`). Pydantic-validated sections: `[main]`, `[data]`, `[logging]`, `[trace]` (see `igscraper.config`).
- **Mode selection** (overwrites `[main].mode` at runtime): see README "How the run picks mode" — URL file wins if `[data].urls_filepath` exists; else profile targets; else no scrape.

## Preconditions

- **Postgres preflight** (`src/igscraper/cli.py`): before `Pipeline` import, the process connects with `PUGSY_PG_*` / defaults and requires `public.crawled_posts` and `public.crawled_comments` via `to_regclass`. Failure is **`SystemExit`** with a concrete hint (not a silent continue).
- **Cookies:** valid cookie JSON path per `[data].cookie_file` (see README "Authenticate").

## Outputs

- JSONL / metadata paths under `[data].*` placeholders (`{output_dir}`, `{target_profile}`, `{trace}.thor_worker_id`, etc. — see [docs/configuration-and-integration.md](../configuration-and-integration.md)).
- Optional GCS upload and enqueue of `gs://…` URIs when `[main].push_to_gcs = 1`; otherwise local absolute paths enqueued.
- Timing / structured logs including `thor_worker_id` when pipeline emits timing events.

## Vocabulary (status-like fields)

Use consistently in plans, logs, and runbooks:

| Term | Meaning |
|------|---------|
| **status** | Coarse outcome of a step or run (`success`, `failed`, …). |
| **terminal** | Failure that will not self-heal without config/account/ops change (e.g. missing tables, hard login wall). |
| **retryable** | Transient: backoff, refresh cookie, or single selector tweak may recover. |
| **partial_success** | Some posts/comments persisted; others skipped or empty by design — must be **explicit** in the code path, not an accident. |
| **freshness** | How recent cookies/capture are relative to the run (stale cookie → false "success"). |
| **error_code** | Stable machine-readable tag when present (prefer existing logger conventions). |

## Non-goals

- This contract does **not** guarantee Instagram DOM or GraphQL stability; see [audit-output-igscraper/executive_summary.md](../../audit-output-igscraper/executive_summary.md).
