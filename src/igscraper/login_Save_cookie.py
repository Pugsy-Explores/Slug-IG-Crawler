from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# macOS: before selenium (and chromedriver) — required for fork-safety when Chrome spawns.
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from igscraper.chrome_compat import (
    macos_google_chrome_binary_if_present,
    try_strip_quarantine_macos,
)
from igscraper.chrome_versions import assert_chrome_and_chromedriver_major_match
from igscraper.paths import (
    get_cached_browser_binaries,
    get_cookie_cache_dir,
    get_cookie_capture_chrome_user_data_dir,
    get_latest_cookie_path,
)


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")

# Run browser in a subprocess (see capture_login_cookies). Set to "1" to force in-process
# (e.g. debugging) — may crash when launched from IDEs with Chrome for Testing on macOS.
_NO_SUBPROCESS_ENV = "IGSCRAPER_COOKIE_NO_SUBPROCESS"
# Set to 1 to skip --user-data-dir (ephemeral profile; debug corrupted profile crashes).
_OMIT_USER_DATA_ENV = "IGSCRAPER_OMIT_CHROME_USER_DATA_DIR"
# Set to 1 to use ~/.slug/chrome-user-data/save-cookie/<user>/ (default is ephemeral, like the
# pinned Linux-ish script that worked without --user-data-dir).
_USE_PERSISTENT_PROFILE_ENV = "IGSCRAPER_COOKIE_USE_USER_DATA_DIR"
_WORKER_ARG = "__cookie_worker__"

# Match SeleniumBackend / Docker: Linux-like fingerprint for Instagram cookie capture.
_LINUXISH_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/143.0.0.0 Safari/537.36"
)
@dataclass
class CookieCaptureResult:
    username: str
    browser_version: str
    cookie_count: int
    cookie_path: Path
    latest_path: Path


def _safe_segment(raw: str, fallback: str) -> str:
    cleaned = _SAFE_SEGMENT_RE.sub("_", (raw or "").strip()).strip("._-")
    return cleaned or fallback


def _resolve_cookie_capture_binaries() -> tuple[str, str]:
    """
    Resolve Chrome + ChromeDriver for cookie capture (both required; majors checked before launch).

    Order:
    1) ``CHROME_BIN`` and ``CHROMEDRIVER_BIN`` when both set.
    2) Otherwise the cached pair from ``Slug-Ig-Crawler bootstrap`` under ``~/.slug/browser/...``.

    Raises:
        RuntimeError: If only one env var is set, or bootstrap cache is incomplete.
    """
    chrome = (os.environ.get("CHROME_BIN") or "").strip() or None
    driver = (os.environ.get("CHROMEDRIVER_BIN") or "").strip() or None

    if chrome and driver:
        return chrome, driver
    if chrome or driver:
        raise RuntimeError(
            "Set both CHROME_BIN and CHROMEDRIVER_BIN to explicit paths, or unset both to use "
            "the Chrome + ChromeDriver pair from Slug-Ig-Crawler bootstrap (~/.slug/browser/...)."
        )

    c_cached, d_cached = get_cached_browser_binaries()
    if c_cached and d_cached:
        return str(c_cached), str(d_cached)

    # macOS: stable Chrome under /Applications + chromedriver on PATH (e.g. Homebrew).
    c_mac = macos_google_chrome_binary_if_present()
    d_path = shutil.which("chromedriver")
    if c_mac and d_path:
        return c_mac, d_path

    raise RuntimeError(
        "No Chrome/ChromeDriver found. Run: Slug-Ig-Crawler bootstrap\n"
        "Or set CHROME_BIN and CHROMEDRIVER_BIN to a matching pair.\n"
        "On macOS you can also install Google Chrome in /Applications and ensure "
        "`chromedriver` is on PATH with a matching major version."
    )


def _warn_if_embedded_ide_terminal() -> None:
    """Cursor/VS Code terminals correlate with Chrome CFT fork crashes on macOS."""
    if sys.platform != "darwin":
        return
    e = os.environ
    tp = (e.get("TERM_PROGRAM") or "").lower()
    if "vscode" in tp or e.get("CURSOR_TRACE_ID") or e.get("CURSOR_AGENT"):
        print(
            "slug-ig-crawler: If Chrome crashes (fork / pre-exec), run save-cookie from "
            "Terminal.app instead of this IDE terminal.\n",
            file=sys.stderr,
            flush=True,
        )


def _build_cookie_filename(browser_version: str, username: str, timestamp: int) -> str:
    version_part = _safe_segment(browser_version, "unknown")
    user_part = _safe_segment(username, "unknown_user")
    return f"{version_part}_{user_part}_{timestamp}.json"


def _chrome_options_for_cookie_capture(username: str) -> Options:
    """
    Minimal Chrome flags aligned with the pinned Linux-ish cookie script (UA + debugging-pipe).

    Default is **no** ``--user-data-dir`` (ephemeral profile). Set ``CHROME_USER_DATA_DIR`` or
    ``IGSCRAPER_COOKIE_USE_USER_DATA_DIR=1`` for ``~/.slug/chrome-user-data/save-cookie/...``.
    ``IGSCRAPER_OMIT_CHROME_USER_DATA_DIR=1`` forces ephemeral even when a path would apply.
    """
    options = Options()
    omit_ud = (os.environ.get(_OMIT_USER_DATA_ENV) or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    want_persistent = (os.environ.get(_USE_PERSISTENT_PROFILE_ENV) or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    raw_ud = (os.environ.get("CHROME_USER_DATA_DIR") or "").strip()
    if omit_ud:
        print(
            "slug-ig-crawler: IGSCRAPER_OMIT_CHROME_USER_DATA_DIR set — "
            "Chrome runs without --user-data-dir (ephemeral profile).\n",
            file=sys.stderr,
            flush=True,
        )
    elif raw_ud or want_persistent:
        user_data = (
            Path(raw_ud).expanduser().resolve()
            if raw_ud
            else get_cookie_capture_chrome_user_data_dir(username)
        )
        user_data.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={user_data}")

    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-features=ChromeWhatsNewUI")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(f"--user-agent={_LINUXISH_UA}")
    options.add_argument("--remote-debugging-pipe")

    return options


def _inject_linuxish_platform_override(driver: webdriver.Chrome) -> None:
    """CDP: navigator.platform Linux (before first navigation), matching the old script."""
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Linux x86_64'
                });
            """
        },
    )


def _cookie_result_to_dict(r: CookieCaptureResult) -> dict[str, Any]:
    return {
        "username": r.username,
        "browser_version": r.browser_version,
        "cookie_count": r.cookie_count,
        "cookie_path": str(r.cookie_path),
        "latest_path": str(r.latest_path),
    }


def _cookie_result_from_dict(d: dict[str, Any]) -> CookieCaptureResult:
    return CookieCaptureResult(
        username=str(d["username"]),
        browser_version=str(d["browser_version"]),
        cookie_count=int(d["cookie_count"]),
        cookie_path=Path(d["cookie_path"]),
        latest_path=Path(d["latest_path"]),
    )


def _capture_login_cookies_impl(username: str) -> CookieCaptureResult:
    """Open browser, wait for manual login, write cookies (runs in worker or in-process)."""
    _warn_if_embedded_ide_terminal()
    chrome_bin, chromedriver_bin = _resolve_cookie_capture_binaries()
    assert_chrome_and_chromedriver_major_match(chrome_bin, chromedriver_bin)
    options = _chrome_options_for_cookie_capture(username)
    options.binary_location = chrome_bin

    try_strip_quarantine_macos(Path(chromedriver_bin))
    service = Service(chromedriver_bin)
    driver = webdriver.Chrome(service=service, options=options)
    try:
        _inject_linuxish_platform_override(driver)
        driver.get("https://www.instagram.com/accounts/login/")
        input("Log in manually, then press Enter here...")

        driver.get("about:blank")
        time.sleep(2)
        driver.get("https://www.instagram.com/")
        time.sleep(5)

        cookies = driver.get_cookies()
        if not cookies:
            raise RuntimeError("No cookies captured - login likely failed")

        browser_version = str(driver.capabilities.get("browserVersion") or "unknown")
        ts = int(time.time())
        out_dir = get_cookie_cache_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        cookie_path = out_dir / _build_cookie_filename(browser_version, username, ts)
        with open(cookie_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)

        latest_path = get_latest_cookie_path()
        shutil.copy2(cookie_path, latest_path)
        return CookieCaptureResult(
            username=username,
            browser_version=browser_version,
            cookie_count=len(cookies),
            cookie_path=cookie_path,
            latest_path=latest_path,
        )
    finally:
        driver.quit()


def _capture_via_fresh_subprocess(username: str) -> CookieCaptureResult:
    """
    Run the browser session in a new Python process.

    Embedded / IDE-hosted interpreters (e.g. Cursor) are often multi-threaded; Chrome for
    Testing then hits macOS fork-safety crashes (``multi-threaded process forked``). A clean
    ``python -m ...`` child avoids spawning Chrome from that environment.
    """
    fd, out_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        env = os.environ.copy()
        if sys.platform == "darwin":
            env.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")
        cmd = [
            sys.executable,
            "-m",
            "igscraper.login_Save_cookie",
            _WORKER_ARG,
            username,
            out_path,
        ]
        proc = subprocess.run(
            cmd,
            stdin=sys.stdin,
            env=env,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Cookie capture worker exited with code {proc.returncode}. "
                f"Ensure Chrome and ChromeDriver major versions match (run bootstrap). "
                f"Or set {_NO_SUBPROCESS_ENV}=1 only for debugging."
            )
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        return _cookie_result_from_dict(data)
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def capture_login_cookies(username: str) -> CookieCaptureResult:
    """
    Open Instagram login page, wait for manual login, and save cookies as JSON.

    Files are saved in ``~/.slug/cookies`` with filename format:
    ``<browserVersion>_<username>_<timestamp>.json`` plus a copied ``latest.json`` pointer.

    Uses **bootstrap** Chrome + ChromeDriver from ``~/.slug/browser/`` (or both ``CHROME_BIN`` and
    ``CHROMEDRIVER_BIN``). **Major versions are checked** before starting the browser.

    Browser options follow the Linux-UA + ``--remote-debugging-pipe`` + CDP ``navigator.platform``
    pattern (default **ephemeral** profile unless ``CHROME_USER_DATA_DIR`` or
    ``IGSCRAPER_COOKIE_USE_USER_DATA_DIR=1``).

    On macOS, capture runs in a **subprocess** by default (IDE fork safety). Set
    ``IGSCRAPER_COOKIE_NO_SUBPROCESS=1`` to force in-process.
    """
    username = (username or "").strip()
    if not username:
        raise ValueError("Instagram username cannot be empty")

    if (os.environ.get(_NO_SUBPROCESS_ENV) or "").strip() == "1":
        return _capture_login_cookies_impl(username)
    return _capture_via_fresh_subprocess(username)


def main() -> None:
    username = input("Enter Instagram username for this session: ").strip()
    result = capture_login_cookies(username)
    print(
        f"Saved {result.cookie_count} cookies for '{result.username}' to {result.cookie_path}\n"
        f"Updated latest pointer: {result.latest_path}"
    )


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == _WORKER_ARG:
        result = _capture_login_cookies_impl(sys.argv[2])
        out = sys.argv[3]
        with open(out, "w", encoding="utf-8") as f:
            json.dump(_cookie_result_to_dict(result), f)
        sys.exit(0)
    main()
