# Slug-Ig-Crawler — reference

This document is part of the [Slug-Ig-Crawler](../README.md) documentation. Paths are relative to the repository root unless noted.

# Configuration

### Trace (`[trace]`)

`Pipeline` requires a non-empty **`[trace].thor_worker_id`** in the config file used for a full run. It is used for structured logs, enqueue metadata, and Chrome profile suffixing. Orchestrators typically inject a job-specific id.

### Configuration File Structure

The application uses TOML configuration files with the following structure:

```toml
[main]
mode = 1  # May be overwritten at runtime; see "Runtime mode selection"
target_profiles = [
    { name = "jaat.aesthetics", num_posts = 10 },
]
headless = false
enable_screenshots = false  # Set to true to enable screenshot capture and video generation
use_docker = false  # Set to true when running in Docker
batch_size = 2
fetch_comments = true
fetch_replies = true
max_comments = 130
scrape_using_captured_requests = true
rate_limit_seconds_min = 2
rate_limit_seconds_max = 4
max_retries = 3
save_every = 2
gcs_bucket_name = "pugsy_ai_crawled_data"  # GCS bucket for video uploads (automatically sanitized if path-like)
consumer_id = "default_consumer"  # Consumer ID for video naming (automatically sanitized)

[data]
output_dir = "outputs"
shot_dir = "{output_dir}/{date}/screens"  # Screenshot directory (used for video generation)
cookie_file = "~/.slug/cookies/latest.json"
posts_path = "{output_dir}/{date}/{target_profile}/posts_{target_profile}_{datetime}.txt"
metadata_path = "{output_dir}/{date}/{target_profile}/metadata_{target_profile}.jsonl"
post_entity_path = "{output_dir}/{date}/{target_profile}/post_entity_{target_profile}_{datetime}.jsonl"
profile_path = "{output_dir}/{date}/{target_profile}/profile_data_{target_profile}_{datetime}.jsonl"
schema_path = "src/igscraper/flatten_schema.yaml"
post_page_data_key = [
    "xdt_api__v1__media__media_id__comments__connection",
    "xdt_api__v1__media__media_id__comments__parent_comment_id__child_comments__connection"
]
profile_page_data_key = ["xdt_api__v1__feed__user_timeline_graphql_connection"]

[logging]
level = "DEBUG"
log_dir = "outputs/logs"
log_format = "%(asctime)s [%(levelname)s/%(processName)s] %(name)s: %(message)s"
date_format = "%Y-%m-%d %H:%M:%S"

[trace]
thor_worker_id = "your-worker-or-job-id"
```

A full sanitized template is **`config.example.toml`** in the repository root.

### Path Placeholders

Path strings support the following placeholders that are automatically expanded:

- `{output_dir}`: Base output directory
- `{target_profile}`: Current profile name
- `{date}`: Current date in `YYYYMMDD` format
- `{datetime}`: Current datetime in `YYYYMMDD_HHMM` format

---

## External services and infrastructure

This section lists **outbound** integrations (cloud, database, HTTP) and what is **required by the config schema** vs **required only when a code path runs**.

### Required TOML sections

`load_config` validates a **`Config`** with **`[main]`**, **`[data]`**, **`[logging]`**, and **`[trace]`** only. There is no message queue or broker section.

### Instagram and the browser (always for scraping)

| Item | Purpose |
|------|--------|
| **HTTPS to `instagram.com` (and related CDN domains)** | Selenium drives a real browser; there is **no** separate Instagram API key. Session auth uses **`[data].cookie_file`** (JSON cookies on disk). |
| **GraphQL / XHR data** | Parsed from **Chrome performance logs** (captured requests), not from a standalone HTTP client to a documented public API. |

### Google Cloud Storage (when upload paths run)

`SeleniumBackend` constructs `google.cloud.storage.Client()` and uses **`[main].gcs_bucket_name`** for:

- **`UploadAndEnqueue.upload_and_enqueue`** — uploads JSONL artifacts and enqueues (see PostgreSQL below). Triggered from `on_posts_batch_ready` / `on_comments_batch_ready` when those batches complete.
- **`upload_video_to_gcs`** — when `enable_screenshots` is true, uploads the shutdown MP4 to the same bucket under `vid_log/`.

**Setup:** Application Default Credentials, or **`GOOGLE_APPLICATION_CREDENTIALS`** pointing to a service account JSON with **write** access to the configured bucket. Without valid credentials, these steps fail when executed.

**Path rule:** `services/upload_enqueue.py` builds object names from local paths that contain the marker **`/outputs/`** (default `GcsUploadConfig.outputs_marker`). Typical layouts use something like `.../outputs/<date>/...` so uploads resolve correctly.

### PostgreSQL (when enqueue runs)

`igscraper/services/enqueue_client.py` **`FileEnqueuer`** inserts rows after a successful GCS upload, using **`psycopg`** with DSN from environment. Env files are loaded in order: **`~/.slug/.env`** (if present), then **`ENV_FILE`** or **`.env`** in the current working directory (project file **overrides** the cache file for duplicate keys).

| Variable | Role (defaults in code) |
|----------|-------------------------|
| `PUGSY_PG_HOST` | Host (`localhost`) |
| `PUGSY_PG_PORT` | Port (`5432` default; use `5433` if Postgres listens on a Docker-mapped port) |
| `PUGSY_PG_USER` | User (`postgres` when unset on Linux; on **macOS** defaults to your **login** — Homebrew often has no `postgres` role) |
| `PUGSY_PG_PASSWORD` | Password (empty default) |
| `PUGSY_PG_DATABASE` | Database name (`postgres` when unset — typical local default; **override for production**) |

Tables: **`crawled_posts`** and **`crawled_comments`** (see docstring in `enqueue_client.py` for expected columns, including **`thor_worker_id`**).

### Full-video download script (in-process)

When `scrape_using_captured_requests` is false and DOM media extraction yields videos, `services/full_media_download_script.py` **`write_and_run_full_download_script`** runs **in the same process** as the pipeline (writes a bash script under the media path and optionally executes it). No Redis, Celery, or separate worker is used.

### Other HTTP (`requests`)

Helpers in `utils.py` / `downloader.py` may use **`requests`** for ancillary downloads (e.g. media URLs). Those are **not** separate “API accounts”; they use normal HTTPS when those code paths run.

---

## Data Models and Parsing

### GraphQL Model Registry

The application uses a registry-based approach to parse GraphQL API responses:

1. **Model Registration**: Pydantic models are registered with regex patterns matching GraphQL data keys
2. **Network Capture**: Chrome performance logs are captured to extract GraphQL responses
3. **Pattern Matching**: Data keys are matched against registered patterns
4. **Validation**: Responses are validated and structured using Pydantic models
5. **Flattening**: Data is flattened according to schema rules defined in `flatten_schema.yaml`

### Flatten Schema

The `flatten_schema.yaml` file defines rules for extracting and flattening nested GraphQL data structures. It specifies:

- Which keys to extract from responses
- How to flatten nested objects
- Field mappings and transformations

---

## Authentication

### Cookie Generation

Before running the scraper, authentication cookies must be generated:

1. Run `python src/igscraper/login_Save_cookie.py`
2. A Chrome browser window opens to Instagram login page
3. Manually log in to your Instagram account
4. Press Enter in the terminal
5. Cookies are saved to `src/igscraper/cookies_{timestamp}.pkl`

### Cookie Usage

During scraping:

1. `SeleniumBackend.start()` calls `_login_with_cookies()`
2. Browser navigates to `https://www.instagram.com/`
3. Cookies are loaded from the pickle file
4. Cookies are added to the WebDriver session
5. Page is refreshed to apply authentication

---
