**Cross-repo vocabulary:** [shared-vocabulary.md](shared-vocabulary.md) (`trace_id`, `status`, `error_code`).

# Contract: Thor handshake (worker identity + Postgres)

Downstream orchestration (e.g. **Thor**) expects the scraper to identify work and enqueue durable paths with a **worker correlation id**.

## Config: `[trace].thor_worker_id`

- **Required** for real pipeline runs: non-empty string in TOML `[trace]` section.
- **Validation:** `load_config` requires `thor_worker_id` when `[trace]` is present; `Pipeline` rejects blank values. If `[trace]` is omitted entirely, config loader may use a placeholder until `Pipeline` validates — see `src/igscraper/tests/test_thor_worker_id.py`.
- **Propagation:** `Pipeline` sets `thor_worker_id` on the backend and on `FileEnqueuer`. SQL `INSERT` into `crawled_posts` / `crawled_comments` includes the `thor_worker_id` column.
- **Observability:** structured timing logs include `thor_worker_id` (same test module).

## Postgres alignment

- **Preflight tables:** `public.crawled_posts`, `public.crawled_comments` must exist before the pipeline starts (`cli.py` preflight). Apply schema via `Slug-Ig-Crawler bootstrap --setup-postgres` or `scripts/postgres_setup.sql` as documented in README.
- **Environment:** `PUGSY_PG_HOST`, `PUGSY_PG_PORT`, `PUGSY_PG_USER`, `PUGSY_PG_PASSWORD`, `PUGSY_PG_DATABASE` (and `~/.slug/.env` after bootstrap) must match the database Thor uses for dequeue/ingest.

## CLI / argv

- Entrypoint: `Slug-Ig-Crawler` or `Slug-Ig-Crawler --config <path>`.
- Thor typically generates a **job-specific `config.toml`** with `thor_worker_id` set to the worker or job id; the scraper does not invent this value in production paths.

## Failure interpretation

| Symptom | Likely layer |
|---------|----------------|
| `SystemExit` Postgres preflight | Infra / schema — fix DB or run bootstrap. |
| `RuntimeError` missing `thor_worker_id` on enqueue | Config / wiring — fix TOML before blaming IG. |
| Empty comments with healthy DB | Extraction / parser — see [parser-output-contract.md](parser-output-contract.md). |
