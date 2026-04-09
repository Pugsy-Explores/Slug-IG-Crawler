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

## Acceptable use and conflicts

<a id="acceptable-use-and-conflicts"></a>

This software is intended for **research, education, and responsible experimentation** on **public** pages—not as endorsement of high-volume production scraping or any use that conflicts with [Instagram / Meta terms](https://help.instagram.com/581066165581870), [Community Guidelines](https://help.instagram.com/477434623621119), or applicable law. Automated access may be restricted or prohibited depending on context; **you** choose how to use the tool and **you** are responsible for compliance. This project is **not** affiliated with Instagram or Meta. The software is provided **as-is** without warranty; authors and contributors assume **no liability** for misuse, account actions, or legal claims.

---

This repository is **open source** (see the license in the repo root).
