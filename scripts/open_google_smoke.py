#!/usr/bin/env python3
"""
Smoke test: open a URL with Chrome for Testing + ChromeDriver.

**Default** uses the same binaries as the app: ``Slug-Ig-Crawler bootstrap`` caches them under
``~/.slug/browser/<CFT platform>/`` where ``<CFT platform>`` is chosen for **this** OS/arch
(``linux64``, ``mac-arm64``, ``mac-x64``). Run bootstrap first if the cache is empty.

``--repo-bundles`` (optional): use ``chrome-mac-arm64/`` + ``chromedriver-mac-arm64/`` in this
repo (local dev only; not the same as bootstrap on Linux/x64 Mac).

By default uses Selenium-friendly flags (no ``--remote-debugging-pipe``). Use
``--cookie-capture-flags`` to mirror save-cookie (may disconnect in some terminals).
"""
from __future__ import annotations

import argparse
import os
import platform
import sys
import time
import traceback
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
_src = _root / "src"
if _src.is_dir() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from igscraper.chrome_compat import apply_automation_compat_flags, try_strip_quarantine_macos
from igscraper.chrome_versions import assert_chrome_and_chromedriver_major_match, try_version_line
from igscraper.login_Save_cookie import (
    _chrome_options_for_cookie_capture,
    _inject_linuxish_platform_override,
    _warn_if_embedded_ide_terminal,
)
from igscraper.paths import describe_cft_host, get_cached_browser_binaries, resolve_cft_platform


def _repo_mac_arm64_binaries() -> tuple[Path, Path]:
    """Optional repo-local mac-arm64 extract (not from internet/bootstrap)."""
    chrome = (
        _root
        / "chrome-mac-arm64"
        / "Google Chrome for Testing.app"
        / "Contents"
        / "MacOS"
        / "Google Chrome for Testing"
    )
    driver = _root / "chromedriver-mac-arm64" / "chromedriver"
    return chrome, driver


def _options_stable(chrome_bin: str) -> Options:
    options = Options()
    options.binary_location = chrome_bin
    if sys.platform != "darwin":
        apply_automation_compat_flags(options, headless=False)
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    return options


def _print_report_header(
    *,
    source: str,
    cft_platform: str,
    chrome_p: Path,
    driver_p: Path,
) -> None:
    print("open_google_smoke")
    print(f"  host:          {describe_cft_host()}")
    print(f"  CFT platform:  {cft_platform}  (bootstrap JSON key; override: IGSCRAPER_CFT_PLATFORM)")
    print(f"  binary source: {source}")
    print(f"  chrome:        {chrome_p}")
    print(f"  chromedriver:  {driver_p}")
    cv = try_version_line(str(chrome_p))
    dv = try_version_line(str(driver_p))
    print(f"  chrome --version:       {cv or '(n/a)'}")
    print(f"  chromedriver --version: {dv or '(n/a)'}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Smoke test: Chrome + ChromeDriver (bootstrap cache by default)."
    )
    ap.add_argument(
        "--url",
        default="https://www.google.com",
        help="Page to open (default: https://www.google.com)",
    )
    ap.add_argument(
        "--seconds",
        type=float,
        default=8.0,
        help="Seconds to keep the window open before closing (0 = exit right after load)",
    )
    ap.add_argument(
        "--repo-bundles",
        action="store_true",
        help="Use repo chrome-mac-arm64/ + chromedriver-mac-arm64/ instead of ~/.slug/browser cache.",
    )
    ap.add_argument(
        "--cookie-capture-flags",
        action="store_true",
        help=(
            "Use the same Chrome flags as save-cookie (incl. --remote-debugging-pipe + CDP). "
            "Can disconnect DevTools in some environments."
        ),
    )
    args = ap.parse_args()

    if args.repo_bundles:
        cft_platform = "mac-arm64 (repo layout)"
        chrome_p, driver_p = _repo_mac_arm64_binaries()
        source = "repo folders (chrome-mac-arm64, chromedriver-mac-arm64)"
    else:
        try:
            cft_platform = resolve_cft_platform()
        except OSError as e:
            print(f"  result: FAIL ({e})")
            return 1
        c_cached, d_cached = get_cached_browser_binaries(cft_platform)
        if not c_cached or not d_cached:
            cache_root = Path.home() / ".slug" / "browser" / cft_platform
            print("open_google_smoke")
            print(f"  host:          {describe_cft_host()}")
            print(f"  CFT platform:  {cft_platform}")
            print(
                "  result: FAIL (no Chrome/ChromeDriver in cache for this platform).\n"
                f"  Expected under: {cache_root}\n"
                "  Run: Slug-Ig-Crawler bootstrap\n"
                "  Or use --repo-bundles if you keep mac-arm64 binaries in this repo."
            )
            return 1
        chrome_p, driver_p = c_cached, d_cached
        source = f"bootstrap cache (~/.slug/browser/{cft_platform}/)"

    chrome_s, driver_s = str(chrome_p), str(driver_p)
    _print_report_header(
        source=source,
        cft_platform=cft_platform,
        chrome_p=chrome_p,
        driver_p=driver_p,
    )

    if not chrome_p.is_file():
        print("  result: FAIL (missing chrome binary)")
        return 1
    if not driver_p.is_file():
        print("  result: FAIL (missing chromedriver)")
        return 1
    if not os.access(driver_s, os.X_OK):
        print("  result: FAIL (chromedriver is not executable)")
        return 1

    _warn_if_embedded_ide_terminal()

    try:
        _, _, matched_quad = assert_chrome_and_chromedriver_major_match(
            chrome_s, driver_s
        )
        print(f"  exact version match: {matched_quad} (Chrome == ChromeDriver)")
    except Exception as e:
        print(f"  result: FAIL (version check: {e})")
        return 1

    if args.cookie_capture_flags:
        options = _chrome_options_for_cookie_capture("smoke-google")
        options.binary_location = chrome_s
    else:
        options = _options_stable(chrome_s)
    try_strip_quarantine_macos(driver_p)

    driver = None
    try:
        driver = webdriver.Chrome(service=Service(driver_s), options=options)
        if args.cookie_capture_flags:
            driver.get("about:blank")
            _inject_linuxish_platform_override(driver)
        driver.get(args.url)
        title = driver.title
        url = driver.current_url
        print(f"  page title:    {title!r}")
        print(f"  current url:   {url!r}")
        if args.seconds > 0:
            time.sleep(args.seconds)
        print("  result: OK")
        return 0
    except Exception as e:
        print(f"  result: FAIL ({type(e).__name__}: {e})")
        traceback.print_exc(file=sys.stdout)
        return 1
    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
