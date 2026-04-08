"""
Chrome / ChromeDriver version check: full four-part build must match (Selenium / CFT).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

# Chrome / ChromeDriver --version lines include a single canonical build id, e.g. 143.0.7499.192
_QUAD_VERSION_RE = re.compile(r"\b(\d+\.\d+\.\d+\.\d+)\b")


def _quad_version_from_version_line(line: str) -> str:
    """Parse the first ``major.minor.build.patch`` token from a ``--version`` line."""
    m = _QUAD_VERSION_RE.search(line)
    if not m:
        raise RuntimeError(
            f"Cannot parse four-part Chrome version from line: {line!r} "
            "(expected something like 143.0.7499.192)"
        )
    return m.group(1)


def _first_version_line(binary_path: str) -> str:
    out = subprocess.check_output([binary_path, "--version"], text=True, timeout=60)
    first = out.strip().splitlines()[0] if out.strip() else out.strip()
    return first


def try_version_line(binary_path: str) -> str | None:
    """First line of ``binary --version``, or ``None`` if missing or unusable."""
    if not Path(binary_path).is_file():
        return None
    try:
        return _first_version_line(binary_path)
    except (
        OSError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        RuntimeError,
    ):
        return None


def assert_chrome_and_chromedriver_major_match(
    chrome_bin: str, chromedriver_bin: str
) -> tuple[str, str, str]:
    """
    Ensure Chrome and ChromeDriver report the **same** four-part version
    (``major.minor.build.patch`` from ``--version``).

    Selenium requires a compatible pair; for Chrome for Testing, the driver build must match
    the browser build exactly.

    Returns ``(chrome_version_line, chromedriver_version_line, matched_quad)`` on success.

    Raises:
        RuntimeError: If versions differ or ``--version`` output is unusable.
    """
    c_line = _first_version_line(chrome_bin)
    d_line = _first_version_line(chromedriver_bin)
    c_quad = _quad_version_from_version_line(c_line)
    d_quad = _quad_version_from_version_line(d_line)
    if c_quad != d_quad:
        raise RuntimeError(
            "Chrome and ChromeDriver four-part versions must match exactly.\n"
            f"  Chrome ({chrome_bin}): {c_quad}  ({c_line})\n"
            f"  ChromeDriver ({chromedriver_bin}): {d_quad}  ({d_line})\n"
            "Re-download a matching pair (e.g. Slug-Ig-Crawler bootstrap) or set "
            "CHROME_BIN and CHROMEDRIVER_BIN to a matching pair."
        )
    return c_line, d_line, c_quad
