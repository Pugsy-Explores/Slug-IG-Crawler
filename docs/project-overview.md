# Slug-Ig-Crawler — reference

This document is part of the [Slug-Ig-Crawler](../README.md) documentation. Paths are relative to the repository root unless noted.

# What this repository is

- **Stack:** Python 3, **Selenium** (+ **selenium-wire** for captured network traffic), **Pydantic** config, optional **GCS** and **Postgres** (`psycopg`) for artifact handoff.
- **Entry point:** `Slug-Ig-Crawler` → `Pipeline` → `SeleniumBackend` → page objects and utilities. Pass `--config /path/to/config.toml`, or omit it when `~/.slug/config.toml` exists (e.g. after `Slug-Ig-Crawler bootstrap`).
- **Outputs:** JSONL and related files under configurable paths; when `push_to_gcs = 1`, batches can be uploaded and **enqueued** (`crawled_posts` / `crawled_comments`). See `scripts/postgres_setup.sql` for the DB schema.
- **Operations note:** Job orchestrators (e.g. **Thor**) may generate configs from their own templates and run the same CLI inside Docker; the main README does not replace Thor’s own docs.

---

## Objectives & scope

- Research, education, and careful automation against **public** pages.
- **Transparency** in how data is collected (browser + captured requests).
- **Traceability** via `thor_worker_id`, structured logs, and optional DB rows.

**You** are responsible for compliance with [Instagram / Meta terms](https://help.instagram.com/581066165581870), applicable law, and your own risk tolerance.

---

## Features

- **Profile mode** — scrape by handle from `[main].target_profiles`.
- **URL file mode** — scrape from a list file when `[data].urls_filepath` exists on disk (overrides profile mode).
- **Captured GraphQL** — optional `scrape_using_captured_requests` path for comment/post data via performance logs.
- **Local media + optional full-video download** — in-process script when not using captured-requests path for some media flows.
- **GCS + Postgres handoff** — upload JSONL and enqueue `gs://` URIs (or **local paths** when `push_to_gcs = 0`).
- **Screenshots → MP4** — optional `enable_screenshots` with shutdown upload (respects `push_to_gcs`).
- **Docker or local Chrome** — `use_docker`, `headless`, env overrides `CHROME_BIN` / `CHROMEDRIVER_BIN`.
- **Observability** — JSON timing events (`pipeline_total_time`, `pipeline_active_time`) and structured fields including `thor_worker_id`.

---

## Key configuration flags

These are the knobs people usually need first. Full TOML lives in **`config.example.toml`**.

| Flag / section | Role |
|----------------|------|
| **`[main].target_profiles`** | Profile mode: list of `{ name, num_posts }`. |
| **`[data].urls_filepath`** | If this path **exists**, URL-file mode wins; otherwise profile mode. |
| **`[main].scrape_using_captured_requests`** | Prefer GraphQL capture from network logs vs. heavier DOM-only flows where applicable. |
| **`[main].push_to_gcs`** | `1` = upload JSONL to GCS and store `gs://...` in DB; `0` = no GCS, enqueue **absolute local paths**; also affects screenshot video upload/cleanup. |
| **`[main].gcs_bucket_name`** | Target bucket when `push_to_gcs = 1` and upload paths run. |
| **`[main].use_docker` / `headless`** | Browser environment: container vs. local; visible vs. headless. |
| **`[main].enable_screenshots`** | Capture WebP frames and generate/upload MP4 on shutdown (see `push_to_gcs`). |
| **`[trace].thor_worker_id`** | **Required** for `Pipeline`; used in logs, enqueue, and naming. |
| **`PUGSY_PG_*` env vars** | Postgres connection for `FileEnqueuer` (see `enqueue_client.py`). |
| **`GOOGLE_APPLICATION_CREDENTIALS`** | Typical GCP auth for GCS when uploading. |

**Environment overrides for binaries:** `CHROME_BIN`, `CHROMEDRIVER_BIN` beat optional `[main].chrome_binary_path` / `chromedriver_binary_path`. On **macOS**, if neither env nor config nor `~/.slug/browser` cache supplies Chrome, the pipeline falls back to **`/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`** when that file exists. **`IGSCRAPER_OMIT_CHROME_USER_DATA_DIR=1`** (save-cookie and `run`) skips `--user-data-dir` for debugging corrupted profiles.
