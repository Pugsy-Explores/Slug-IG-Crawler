"""
Helpers to detect OS / Linux family for local PostgreSQL installation.

Used by tests and optionally by tooling; the actual install is
``scripts/install_postgres_local.sh``.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Literal

LinuxFamily = Literal["debian", "rhel", "unknown"]


def _parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip().lower()
        v = v.strip().strip('"').strip("'")
        out[k] = v
    return out


def detect_linux_family(*, root: Path = Path("/")) -> LinuxFamily:
    """
    Best-effort Debian vs RHEL-style family for package commands.

    *root* is only for unit tests (fake filesystem roots).
    """
    if sys.platform != "linux":
        return "unknown"

    if (root / "etc/debian_version").is_file():
        return "debian"

    rel = root / "etc/os-release"
    if rel.is_file():
        try:
            data = _parse_os_release(rel.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            data = {}
        id_ = (data.get("id") or "").lower()
        id_like = (data.get("id_like") or "").lower()
        deb_like = (
            id_ in ("debian", "ubuntu", "linuxmint", "pop")
            or "debian" in id_like
            or "ubuntu" in id_like
        )
        rhel_like = (
            id_ in ("fedora", "rhel", "centos", "rocky", "almalinux", "amzn")
            or "rhel" in id_like
            or "fedora" in id_like
        )
        if deb_like and not rhel_like:
            return "debian"
        if rhel_like:
            return "rhel"

    if (root / "etc/redhat-release").is_file():
        return "rhel"

    return "unknown"


def has_psql() -> bool:
    return shutil.which("psql") is not None


def install_script_hint() -> str:
    """One-line hint for users (e.g. README)."""
    return "Run `./scripts/install_postgres_local.sh` from the repository root (macOS + Linux)."
