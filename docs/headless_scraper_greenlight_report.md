# Standalone Headless Scraper Readiness Report
Date: 2026-04-25
Scope: Direct `ig_profile_scraper` validation (no Thor end-to-end run).

## Executive Verdict
**YELLOW**

The scraper is operational for real headless collection with valid local cookies and matching Chrome/ChromeDriver, but there is one non-trivial automation risk: an interactive `input()` prompt in navigation guard logic can break unattended runs unless stdin is handled.

## What Run Method Is Canonical
- CLI entrypoint from repo truth: `Slug-Ig-Crawler` / `igscraper` / `python -m igscraper.cli` (`pyproject.toml` scripts + `src/igscraper/cli.py`).
- Canonical run command shape:
  - `python3 -m igscraper.cli run --config <path-to-toml>`
- Mode selection truth from pipeline:
  - URL-file mode wins only if `[data].urls_filepath` exists on disk.
  - Otherwise profile mode runs if `[main].target_profiles` is non-empty.
- DB preflight is mandatory in `cli.py` before pipeline start:
  - checks DB connectivity and `crawled_posts` + `crawled_comments`.
  - pulls defaults from `~/.slug/.env` and applies those as runtime defaults.

## What Browser Runtime Was Verified
- Browser binaries discovered by scraper CLI:
  - Chrome: `~/.slug/browser/mac-arm64/.../Google Chrome for Testing`
  - ChromeDriver: `~/.slug/browser/mac-arm64/.../chromedriver`
- Version lock verified:
  - Chrome `143.0.7499.169`
  - ChromeDriver `143.0.7499.169`
- Smoke checks passed in both normal and cookie-capture-like flag sets:
  - `PYTHONPATH=src python3 scripts/open_google_smoke.py --seconds 1`
  - `PYTHONPATH=src python3 scripts/open_google_smoke.py --cookie-capture-flags --seconds 1`
  - both returned `result: OK`.

## Cookie Source Used (Redacted/Generalized)
- Local cookie cache path family used:
  - `~/.slug/cookies/latest.json` (pointer)
  - `~/.slug/cookies/<version>_<username>_<ts>.json`
- Structural validation:
  - JSON list of cookie dicts, expected keys present (`name`, `value`, `domain`, `path`, etc.).
  - domain preview matched `.instagram.com`.
- No cookie secret values exposed in this report.

## Exact Test Executed
- Temporary minimal config created for low-risk run:
  - `scripts/headless_greenlight_config.toml`
  - profile mode, one public target (`memezar`), `num_posts=1`
  - `headless=true`, `use_docker=false`, `push_to_gcs=0`, `fetch_comments=false`
  - cookie source: `~/.slug/cookies/latest.json`
- First real run command:
  - `PUGSY_PG_* ... PYTHONPATH=src python3 -m igscraper.cli run --config scripts/headless_greenlight_config.toml`
  - collected data but exited non-zero due interactive prompt/shutdown behavior.
- Retry command (non-interactive stdin-safe):
  - `printf '
' | PUGSY_PG_* ... PYTHONPATH=src python3 -m igscraper.cli run --config scripts/headless_greenlight_config.toml`
  - exited cleanly (`exit 0`).

## Result
- Browser launched and passed version checks.
- Cookie login succeeded (`✅ Logged in successfully (cookie bootstrap)`).
- Target profile accessed and parsed.
- Real artifacts produced under `outputs/greenlight/20260425/memezar/`:
  - `posts_memezar_20260425_2043.txt`
  - `graphql_keys_memezar_20260425_2043.jsonl`
  - `profile_data_memezar_20260425_2043.jsonl`
  - `profile_data_memezar_20260425_2043_sorted.jsonl`
- DB enqueue evidence observed in scraper runtime DB target (`postgres` via `~/.slug/.env`):
  - `crawled_posts` contains new rows with `thor_worker_id='greenlight-standalone'`
  - file path includes `profile_data_memezar_20260425_2043_sorted.jsonl`.
- Runtime duration:
  - shell elapsed: ~42s
  - pipeline timing log: ~27s total profile pipeline time.

## If Failed
- Initial failure mode:
  - process exited non-zero (`134`) after successful scraping work.
- Root cause:
  - interactive navigation guard in `src/igscraper/chrome.py` emits:
    - `⚠️ Suspicious navigation: ...`
    - `input("Press Enter to continue after checking...")`
  - this is unsafe for unattended/headless automation.
- Confidence in root cause: **high** (direct runtime evidence).
- Smallest next fix:
  - gate the blocking `input()` behind an opt-in env flag (default non-interactive), or remove prompt from runtime path.

## Exact Thor Readiness Impact
- **Can Thor proceed now?** **No (not yet ideal for unattended runs).**
- Why:
  - scraper core is healthy (browser + cookies + collection + enqueue), but interactive prompt risk can destabilize autonomous worker execution if triggered.
- Practical interim workaround:
  - non-interactive stdin injection can bypass in ad-hoc local runs, but this is not a robust production behavior.
- Recommendation before Thor live spine:
  - patch `src/igscraper/chrome.py` to make navigation guard non-blocking by default, then rerun this same minimal standalone test once.
