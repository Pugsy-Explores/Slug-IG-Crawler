from __future__ import annotations

import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from igscraper.paths import get_cached_browser_binaries, get_cookie_cache_dir, get_latest_cookie_path


_SAFE_SEGMENT_RE = re.compile(r"[^a-zA-Z0-9._-]+")


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


def _resolve_cookie_capture_binaries() -> tuple[Optional[str], Optional[str]]:
    """
    Resolve Chrome + ChromeDriver for cookie capture.

    Order:
    1) CHROME_BIN / CHROMEDRIVER_BIN env vars
    2) cached bootstrap pair under ~/.slug/browser/<platform>/
    3) None (let Selenium use system defaults/PATH)
    """
    chrome = (os.environ.get("CHROME_BIN") or "").strip() or None
    driver = (os.environ.get("CHROMEDRIVER_BIN") or "").strip() or None
    if chrome and driver:
        return chrome, driver

    c_cached, d_cached = get_cached_browser_binaries()
    if not chrome and c_cached:
        chrome = str(c_cached)
    if not driver and d_cached:
        driver = str(d_cached)
    return chrome, driver


def _build_cookie_filename(browser_version: str, username: str, timestamp: int) -> str:
    version_part = _safe_segment(browser_version, "unknown")
    user_part = _safe_segment(username, "unknown_user")
    return f"{version_part}_{user_part}_{timestamp}.json"


def capture_login_cookies(username: str) -> CookieCaptureResult:
    """
    Open Instagram login page, wait for manual login, and save cookies as JSON.

    Files are saved in ``~/.slug/cookies`` with filename format:
    ``<browserVersion>_<username>_<timestamp>.json`` plus a copied ``latest.json`` pointer.
    """
    username = (username or "").strip()
    if not username:
        raise ValueError("Instagram username cannot be empty")

    chrome_bin, chromedriver_bin = _resolve_cookie_capture_binaries()
    options = Options()
    if chrome_bin:
        options.binary_location = chrome_bin

    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-features=ChromeWhatsNewUI")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--remote-debugging-pipe")

    service = Service(chromedriver_bin) if chromedriver_bin else Service()
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        input("Log in manually, then press Enter here...")

        driver.get("about:blank")
        time.sleep(2)
        driver.get("https://www.instagram.com/")
        time.sleep(4)

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


def main() -> None:
    username = input("Enter Instagram username for this session: ").strip()
    result = capture_login_cookies(username)
    print(
        f"Saved {result.cookie_count} cookies for '{result.username}' to {result.cookie_path}\n"
        f"Updated latest pointer: {result.latest_path}"
    )


if __name__ == "__main__":
    main()
