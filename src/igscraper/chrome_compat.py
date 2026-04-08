"""
Chrome + ChromeDriver conveniences for Selenium (macOS/Linux automation pitfalls).

- Default Google Chrome path on macOS when Selenium cannot resolve the binary.
- Shared automation flags (no-sandbox, dev-shm, gpu, start-maximized).
- Strip Gatekeeper quarantine from downloaded Chrome / ChromeDriver (bootstrap / first run).
- Ensure executable bits on Chrome / ChromeDriver (zip extracts sometimes omit ``+x``).
"""
from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from selenium.webdriver.chrome.options import Options

# Standard install path for Google Chrome on macOS (not Chrome for Testing).
MACOS_GOOGLE_CHROME_BIN = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
)


def macos_google_chrome_binary_if_present() -> Optional[str]:
    """Return the stable Chrome binary path if the file exists."""
    if sys.platform != "darwin":
        return None
    p = Path(MACOS_GOOGLE_CHROME_BIN)
    return str(p.resolve()) if p.is_file() else None


def try_chmod_plus_x(path: Path) -> None:
    """
    Ensure *path* has executable bits (zip / archive extracts often omit ``+x``).

    Best-effort: ignores missing files and chmod errors (e.g. read-only filesystem).
    """
    if not path.is_file():
        return
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass


def apply_automation_compat_flags(options: Options, *, headless: bool) -> None:
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    # ONLY ONE debugging config
    options.add_argument("--remote-debugging-port=9222")

    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")

    # isolate profile (good)
    options.add_argument("--user-data-dir=/tmp/chrome-test-profile")

    if headless:
        options.add_argument("--headless=new")

def try_strip_quarantine_macos(path: Path) -> None:
    """
    Remove ``com.apple.quarantine`` from a binary (e.g. Homebrew / downloaded chromedriver).

    Equivalent to: ``xattr -d com.apple.quarantine <path>`` (no-op if missing).
    """
    if sys.platform != "darwin" or not path.is_file():
        return
    try:
        subprocess.run(
            ["xattr", "-d", "com.apple.quarantine", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        pass


def try_strip_quarantine_tree_macos(root: Path) -> None:
    """
    Recursively remove ``com.apple.quarantine`` under *root* (e.g. ``~/.slug/browser``).

    Equivalent to ``xattr -dr com.apple.quarantine <root>`` — helps Chrome for Testing
    after download when Gatekeeper tagged the tree.
    """
    if sys.platform != "darwin" or not root.exists():
        return
    try:
        subprocess.run(
            ["xattr", "-dr", "com.apple.quarantine", str(root.resolve())],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        pass
