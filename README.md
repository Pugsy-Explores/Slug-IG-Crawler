# Slug-Ig-Crawler

[![CI](https://img.shields.io/github/actions/workflow/status/Pugsyfy/Slug-IG-Crawler/ci.yml?branch=main&label=CI)](https://github.com/Pugsyfy/Slug-IG-Crawler/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Pugsyfy/Slug-IG-Crawler?style=social)](https://github.com/Pugsyfy/Slug-IG-Crawler/stargazers)
[![PyPI version](https://img.shields.io/pypi/v/slug_ig_crawler.svg)](https://pypi.org/project/slug-ig-crawler/)
[![Python versions](https://img.shields.io/pypi/pyversions/slug_ig_crawler.svg)](https://pypi.org/project/slug-ig-crawler/)
[![License](https://img.shields.io/github/license/Pugsyfy/Slug-IG-Crawler)](https://github.com/Pugsyfy/Slug-IG-Crawler/blob/main/LICENSE)
[![PyPI downloads](https://img.shields.io/badge/downloads-see%20PyPI%20stats-0A66C2)](https://pypi.org/project/slug-ig-crawler/)
[![Repo views](https://visitor-badge.laobi.icu/badge?page_id=Pugsyfy.Slug-IG-Crawler&left_text=Repo%20views)](https://github.com/Pugsyfy/Slug-IG-Crawler)

**Slug-Ig-Crawler** (PyPI: `slug-ig-crawler`, import package `igscraper`) drives a real browser (Selenium) to collect **public** Instagram profile data, post metadata, comments, and media, with optional **Google Cloud Storage** uploads and **PostgreSQL** enqueue rows for downstream pipelines. Configuration is **TOML + Pydantic**; orchestration is **CLI → Pipeline → Selenium backend**.

---

## Table of contents

| Topic | Where |
|--------|--------|
| **Quick start** | [Quick start](#quick-start) (below) |
| **`[main]` TOML cheat sheet** | [Main TOML cheat sheet](#main-toml-cheat-sheet) |
| Project overview | [docs/project-overview.md](docs/project-overview.md) |
| Installation | [docs/installation.md](docs/installation.md) |
| Architecture & components | [docs/architecture.md](docs/architecture.md) |
| Configuration & integration | [docs/configuration-and-integration.md](docs/configuration-and-integration.md) |
| Operations (Docker, persistence, troubleshooting, timing) | [docs/operations.md](docs/operations.md) |
| PyPI releases | [docs/PYPI_RELEASE.md](docs/PYPI_RELEASE.md) |
| Changelog | [CHANGELOG.md](CHANGELOG.md) |
| All docs | [docs/index.md](docs/index.md) |

---

<a id="quick-start"></a>

## Quick start

Get the crawler running locally with a working browser, database, and config. For install options (PyPI extras, bootstrap, publishing), see [docs/installation.md](docs/installation.md).

### 1. Set up Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install + bootstrap

```bash
pip install "slug-ig-crawler[all]"
Slug-Ig-Crawler bootstrap
```

This downloads and caches **Chrome for Testing + ChromeDriver**, creates `~/.slug/config.toml`, applies the **Postgres schema** (default: `localhost:5432`, DB: `postgres`), and writes resolved DB config to `~/.slug/.env`.

- macOS (Homebrew): DB user defaults to your system username; other systems often use `postgres`.
- Docker-mapped Postgres port: `export PUGSY_PG_PORT=5433`
- Skip DB setup: `Slug-Ig-Crawler bootstrap --no-setup-postgres`

### 3. Ensure Postgres is running

If Postgres is not already available:

```bash
./scripts/install_postgres_local.sh
```

Manual schema apply: `psql "$YOUR_DATABASE_URL" -f scripts/postgres_setup.sql`. Connection can be set via `PUGSY_PG_*`, project `.env`, or `~/.slug/.env`.

### 4. Authenticate (required)

```bash
Slug-Ig-Crawler save-cookie --username <instagram_username>
```

Then set in `~/.slug/config.toml` (or your config path):

```toml
[data]
cookie_file = "~/.slug/cookies/latest.json"

[trace]
thor_worker_id = "local-dev"
```

For local testing without GCP: `push_to_gcs = 0` under `[main]`.

### 5. Choose input mode

**Profile mode (default):** set `[main].target_profiles` and ensure `[data].urls_filepath` is unset or points to a non-existent file.

**URL file mode:** create a line-per-URL file and set `[data].urls_filepath` to its absolute path.

### 6. Runtime mode

**Local dev:** `[main]` with `use_docker = false`, `headless = false` as needed. **Container:** `use_docker = true` and use the repo’s Docker/compose guidance in [docs/operations.md](docs/operations.md).

### 7. Run

```bash
Slug-Ig-Crawler
# or
Slug-Ig-Crawler --config /path/to/config.toml
```

**Working run:** Chrome starts, requests are captured, data flows to Postgres, no repeated login or crash loops. If something fails, check cookies and DB first, then re-run `Slug-Ig-Crawler bootstrap` if Chrome/Driver versions drift.

Full flag reference and behavior: [docs/project-overview.md](docs/project-overview.md) and [docs/configuration-and-integration.md](docs/configuration-and-integration.md).

---

<a id="main-toml-cheat-sheet"></a>

## Main TOML cheat sheet

Values below live in **`[main]`** unless noted. Defaults and the full template are in **`config.example.toml`** (copy to `config.toml` or use `~/.slug/config.toml` after bootstrap).

### How the run picks “mode”

At **`Pipeline.run()`** the effective mode is chosen in this order; **`[main].mode` in TOML is overwritten** to match.

| Priority | Condition | What runs |
|----------|-----------|-----------|
| 1 | `[data].urls_filepath` is set **and** that path **exists** on disk | **URL-file mode** — one Instagram post/reel URL per line; results keyed by `[main].run_name_for_url_file` (default `url_file_run`). |
| 2 | Else `[main].target_profiles` is **non-empty** | **Profile mode** — each `{ name, num_posts }` is scraped in order. |
| 3 | Else | Logged warning; **no scrape**. |

To stay on profile mode while keeping a `urls_filepath` key in TOML, point it at a path that does **not** exist yet, or remove/comment the line.

### Input and browser

| Key | Definition / use |
|-----|-------------------|
| **`target_profiles`** | List of tables: `name` = handle (no `@`), `num_posts` = positive integer. Profile-mode workload. |
| **`[data].urls_filepath`** | Optional. If present **and** the file exists → URL-file mode wins. Use an absolute path if your cwd varies. |
| **`run_name_for_url_file`** | Label for this URL-file run in logs/results aggregation; must be non-empty in URL-file mode. |
| **`headless`** | `true` = no browser window (typical servers); `false` = visible Chrome (debugging, local dev). |
| **`use_docker`** | `true` = expect Chrome/ChromeDriver paths and flags suitable for the container image; `false` = local binaries (see `CHROME_BIN` / `CHROMEDRIVER_BIN`, optional `chrome_binary_path` / `chromedriver_binary_path`). |
| **`chrome_binary_path`**, **`chromedriver_binary_path`** | Used when env `CHROME_BIN` / `CHROMEDRIVER_BIN` are unset and `use_docker` is `false` (then OS defaults may apply). |

### Artifacts, comments, and capture

| Key | Definition / use |
|-----|-------------------|
| **`push_to_gcs`** | `1` — upload JSONL to GCS and enqueue `gs://…` in Postgres; `0` — no GCS upload, enqueue **absolute local paths**. Also affects screenshot-video upload when enabled. |
| **`gcs_bucket_name`** | Bucket for uploads when `push_to_gcs = 1` and upload paths run. |
| **`scrape_using_captured_requests`** | Prefer GraphQL/network-log capture for comments (and related paths) vs heavier DOM-only flows where applicable. |
| **`fetch_comments`**, **`fetch_replies`**, **`max_comments`** | Whether to collect comments/replies and how deep to go (see template for defaults). |
| **`batch_size`**, **`save_every`**, **`rate_limit_seconds_min`**, **`rate_limit_seconds_max`** | Posts per batch, flush frequency, and random sleep bounds between batches. |
| **`enable_screenshots`** | Periodic WebP captures → MP4 on shutdown; upload/cleanup tied to `push_to_gcs`. |

For **`[data]`** paths (outputs, cookies, GraphQL keys), placeholders like `{output_dir}`, `{date}`, `{target_profile}`, `{datetime}`, and **`[trace].thor_worker_id`** (required for `Pipeline`), see [docs/configuration-and-integration.md](docs/configuration-and-integration.md).

---

## Acceptable use and conflicts

<a id="acceptable-use-and-conflicts"></a>

This software is intended for **research, education, and responsible experimentation** on **public** pages—not as endorsement of high-volume production scraping or any use that conflicts with [Instagram / Meta terms](https://help.instagram.com/581066165581870), [Community Guidelines](https://help.instagram.com/477434623621119), or applicable law. Automated access may be restricted or prohibited depending on context; **you** choose how to use the tool and **you** are responsible for compliance. This project is **not** affiliated with Instagram or Meta. The software is provided **as-is** without warranty; authors and contributors assume **no liability** for misuse, account actions, or legal claims.

---

This repository is **open source** (see the license in the repo root).
