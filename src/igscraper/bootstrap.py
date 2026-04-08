"""
Download Chrome for Testing (pinned **full** version, default ``143.0.7499.169``) + matching ChromeDriver
into ``~/.slug`` and optionally install the bundled sample config at ``~/.slug/config.toml``.
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional
import requests
import psycopg

from igscraper.chrome_compat import try_strip_quarantine_macos
from igscraper.paths import (
    chrome_executable_path_after_extract,
    chromedriver_executable_path_after_extract,
    get_browser_platform_dir,
    get_cached_config_path,
    get_cached_dotenv_path,
    get_chrome_extract_dir,
    get_chromedriver_extract_dir,
    get_slug_cache_dir,
    resolve_cft_platform,
)
from igscraper.pg_env import (
    apply_resolved_to_environ,
    resolve_pg_env_for_bootstrap,
    write_cached_dotenv,
)

# Exact builds (Chrome + ChromeDriver URLs stay in lockstep per version).
CFT_KNOWN_GOOD_JSON_URL = (
    "https://googlechromelabs.github.io/chrome-for-testing/"
    "known-good-versions-with-downloads.json"
)
# Default exact Chrome for Testing build (override with IGSCRAPER_CFT_FULL_VERSION).
DEFAULT_CFT_FULL_VERSION = "143.0.7499.169"


@dataclass
class BootstrapResult:
    ok: bool
    message: str
    cft_platform: str
    chrome_version: str
    chrome_bin: Optional[Path] = None
    chromedriver_bin: Optional[Path] = None
    config_path: Optional[Path] = None
    config_written: bool = False
    postgres_setup_attempted: bool = False
    postgres_setup_ok: Optional[bool] = None
    postgres_message: str = ""


def read_bundled_sample_config_text() -> str:
    """Load packaged ``config.example.toml`` (wheel-safe)."""
    try:
        from importlib.resources import files

        p = files("igscraper").joinpath("config.example.toml")
        return p.read_text(encoding="utf-8")
    except Exception:
        # Editable / dev: fall back next to this package
        here = Path(__file__).resolve().parent / "config.example.toml"
        if here.is_file():
            return here.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "Bundled config.example.toml not found in package; reinstall slug-ig-crawler."
    )


def _resolve_cft_full_version() -> str:
    """Full build id (e.g. ``143.0.7499.169``). Env ``IGSCRAPER_CFT_FULL_VERSION`` overrides default."""
    raw = (os.environ.get("IGSCRAPER_CFT_FULL_VERSION") or "").strip()
    return raw if raw else DEFAULT_CFT_FULL_VERSION


def _cft_pin_marker_path(cft_platform: str) -> Path:
    """Written after a successful download; holds the full pinned ``x.y.z.w`` string."""
    return get_browser_platform_dir(cft_platform) / ".cft-pinned-version"


def validate_cft_download_urls_for_platform(
    cft_platform: str, chrome_url: str, driver_url: str
) -> None:
    """
    Ensure both URLs are https and contain the official per-platform path segment.

    Chrome for Testing publishes separate zips per platform; this catches bad metadata
    or wrong ``platform`` keys before downloading hundreds of MB.
    """
    if not chrome_url.startswith("https://") or not driver_url.startswith("https://"):
        raise RuntimeError(
            "Chrome and ChromeDriver download URLs must use https. "
            f"chrome={chrome_url!r} driver={driver_url!r}"
        )
    slug_by_platform: dict[str, str] = {
        "linux64": "linux64",
        "mac-arm64": "mac-arm64",
        "mac-x64": "mac-x64",
    }
    slug = slug_by_platform.get(cft_platform)
    if not slug:
        raise RuntimeError(f"Unknown CFT platform: {cft_platform!r}")
    if slug not in chrome_url or slug not in driver_url:
        raise RuntimeError(
            f"Download URL platform mismatch for resolved platform {cft_platform!r}: "
            f"expected path segment {slug!r} in both URLs.\n"
            f"  chrome: {chrome_url}\n"
            f"  driver: {driver_url}"
        )


def _fetch_pinned_full_version_download_urls(
    cft_platform: str, full_version: str
) -> tuple[str, str, str]:
    """Return (chrome_version, chrome_zip_url, chromedriver_zip_url) for an exact known-good build."""
    try:
        r = requests.get(CFT_KNOWN_GOOD_JSON_URL, timeout=120)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch Chrome for Testing metadata: {e}") from e

    versions: list[dict[str, Any]] = data.get("versions") or []
    entry: Optional[dict[str, Any]] = None
    for v in versions:
        if str(v.get("version") or "") == full_version:
            entry = v
            break
    if not entry:
        raise RuntimeError(
            f"Chrome for Testing JSON has no known-good entry for version {full_version!r}. "
            "See https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json "
            "or set IGSCRAPER_CFT_FULL_VERSION to a listed build."
        )

    version = str(entry.get("version") or full_version)
    downloads = entry.get("downloads") or {}
    chrome_list = downloads.get("chrome") or []
    driver_list = downloads.get("chromedriver") or []

    def _pick(entries: list[dict[str, Any]], key: str) -> Optional[str]:
        for item in entries:
            if item.get("platform") == key:
                return str(item.get("url") or "")
        return None

    cu = _pick(chrome_list, cft_platform)
    du = _pick(driver_list, cft_platform)
    if not cu or not du:
        raise RuntimeError(
            f"No Chrome/ChromeDriver URLs for version {full_version!r}, "
            f"platform {cft_platform!r} in metadata."
        )
    validate_cft_download_urls_for_platform(cft_platform, cu, du)
    return version, cu, du


def _download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def _extract_zip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)


def _chmod_plus_x(path: Path) -> None:
    if not path.is_file():
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _apply_macos_cft_tree_fixes(chrome_dir: Path, cft_platform: str) -> None:
    """
    macOS CFT fixups for downloaded app bundles.

    For mac-arm64 we run the equivalent of:
    - chmod -R +x "<...>/Google Chrome for Testing.app"
    - xattr -dr com.apple.quarantine "<...>/chrome-mac-arm64/"
    """
    if sys.platform != "darwin" or cft_platform != "mac-arm64":
        return
    cft_root = chrome_dir / "chrome-mac-arm64"
    app_bundle = cft_root / "Google Chrome for Testing.app"
    if app_bundle.exists():
        try:
            subprocess.run(
                ["chmod", "-R", "+x", str(app_bundle)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass
    if cft_root.exists():
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(cft_root)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            pass


def _apply_linux_cft_tree_chmod(chrome_dir: Path, cft_platform: str) -> None:
    """
    Linux CFT fixup: recursively ensure executable bits on extracted browser tree.

    This mirrors the macOS recursive chmod intent, but Linux-only and chmod-only.
    """
    if not sys.platform.startswith("linux") or cft_platform != "linux64":
        return
    cft_root = chrome_dir / "chrome-linux64"
    if not cft_root.exists():
        return
    try:
        subprocess.run(
            ["chmod", "-R", "+x", str(cft_root)],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        pass


def _write_browser_env_to_cached_dotenv(chrome_bin: Path, driver_bin: Path) -> Path:
    """
    Upsert CHROME_BIN and CHROMEDRIVER_BIN in ``~/.slug/.env``.

    This keeps runtime browser resolution deterministic across docker/local runs.
    """
    dotenv_path = get_cached_dotenv_path()
    get_slug_cache_dir().mkdir(parents=True, exist_ok=True)

    existing: list[str] = []
    if dotenv_path.is_file():
        existing = dotenv_path.read_text(encoding="utf-8").splitlines()

    kept: list[str] = []
    for line in existing:
        if line.startswith("CHROME_BIN=") or line.startswith("CHROMEDRIVER_BIN="):
            continue
        kept.append(line)

    if kept and kept[-1] != "":
        kept.append("")
    # Quote values so `. ~/.slug/.env` works even when paths include spaces.
    chrome_q = str(chrome_bin).replace("'", "'\"'\"'")
    driver_q = str(driver_bin).replace("'", "'\"'\"'")
    kept.append(f"CHROME_BIN='{chrome_q}'")
    kept.append(f"CHROMEDRIVER_BIN='{driver_q}'")
    kept.append("")
    dotenv_path.write_text("\n".join(kept), encoding="utf-8")
    return dotenv_path


def ensure_sample_config_in_cache(*, force: bool = False) -> tuple[Path, bool]:
    """
    Copy bundled sample to ``~/.slug/config.toml`` if missing (unless *force*).

    Returns ``(path, written)``.
    """
    dest = get_cached_config_path()
    get_slug_cache_dir().mkdir(parents=True, exist_ok=True)
    if dest.is_file() and not force:
        return dest, False
    text = read_bundled_sample_config_text()
    dest.write_text(text, encoding="utf-8")
    return dest, True


def _default_postgres_setup_sql_path() -> Path:
    # src/igscraper/bootstrap.py -> repo root/scripts/postgres_setup.sql
    return Path(__file__).resolve().parents[2] / "scripts" / "postgres_setup.sql"


def pg_connection_failure_hint(exc: BaseException) -> str:
    """
    Extra context when Postgres TCP connect fails (nothing listening on host:port).

    Typical cause: PostgreSQL server not started or wrong port/host.
    """
    msg = str(exc).lower()
    if "connection refused" not in msg:
        return ""
    lines = [
        "",
        "Hint: PostgreSQL is not accepting connections on that host/port "
        "(server usually not running, or wrong PUGSY_PG_*).",
    ]
    if sys.platform == "darwin":
        lines.append(
            "  macOS: brew services start postgresql@15   # or: brew services start postgresql"
        )
        lines.append("  Check: brew services list | grep -i postgres")
    elif sys.platform.startswith("linux"):
        lines.append(
            "  Linux: sudo systemctl start postgresql   # or postgresql@<version>"
        )
    lines.append(
        "  Or run from repo clone: ./scripts/install_postgres_local.sh"
    )
    lines.append(
        "  To skip DB setup for now: Slug-Ig-Crawler bootstrap --no-setup-postgres"
    )
    return "\n".join(lines)


def pg_role_missing_hint(exc: BaseException) -> str:
    """When the server rejects the configured role (common with Homebrew + user ``postgres``)."""
    msg = str(exc)
    if 'role "postgres" does not exist' not in msg:
        return ""
    lines = [
        "",
        'Hint: Homebrew PostgreSQL often has no database role named "postgres".',
        "  Omit PUGSY_PG_USER (bootstrap defaults to your macOS login), or run: createuser -s postgres",
    ]
    return "\n".join(lines)


def _load_default_postgres_setup_sql() -> tuple[Optional[str], str]:
    """
    Load default postgres setup SQL text.

    Priority:
    1) Bundled package data: igscraper/postgres_setup.sql (works after pip install)
    2) Repository fallback: scripts/postgres_setup.sql (editable/source runs)
    """
    try:
        from importlib.resources import files

        p = files("igscraper").joinpath("postgres_setup.sql")
        return p.read_text(encoding="utf-8"), "package:igscraper/postgres_setup.sql"
    except Exception:
        pass

    fallback = _default_postgres_setup_sql_path()
    if fallback.is_file():
        return fallback.read_text(encoding="utf-8"), str(fallback)
    return None, f"{fallback} (missing)"


def _run_postgres_setup(
    *,
    sql_text: str,
    sql_source: str,
    progress: Optional[Callable[[str], None]] = None,
) -> tuple[bool, str]:
    def _emit(msg: str) -> None:
        if progress:
            progress(msg)

    resolved = resolve_pg_env_for_bootstrap(apply_default_database=True)
    host = resolved.host
    port = resolved.port
    user = resolved.user
    password = resolved.password
    database = resolved.database

    if resolved.used_default_database:
        _emit(
            "PUGSY_PG_DATABASE not set; using local default "
            f"'{database}' (override with env or ~/.slug/.env)."
        )

    _emit(
        "Postgres setup target -> "
        f"host={host} port={port} db={database} user={user}"
    )
    _emit(f"Loading SQL from {sql_source}")
    if not sql_text.strip():
        return False, f"Postgres setup SQL is empty: {sql_source}"

    dsn = (
        f"host={host} port={port} dbname={database} "
        f"user={user} password={password}"
    )
    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            with conn.cursor() as cur:
                _emit("Executing postgres_setup.sql (idempotent statements)...")
                cur.execute(sql_text)
                conn.commit()
                cur.execute(
                    "SELECT to_regclass('public.crawled_posts'), "
                    "to_regclass('public.crawled_comments')"
                )
                posts_tbl, comments_tbl = cur.fetchone()
        if posts_tbl and comments_tbl:
            dotenv_path = write_cached_dotenv(resolved)
            apply_resolved_to_environ(resolved)
            return (
                True,
                "Postgres bootstrap complete: required tables are present. "
                f"Wrote {dotenv_path}",
            )
        return (
            False,
            "Postgres setup ran but required tables were not detected "
            "(crawled_posts, crawled_comments).",
        )
    except Exception as e:
        hint = pg_connection_failure_hint(e) + pg_role_missing_hint(e)
        return False, f"Postgres setup failed: {e}{hint}"


def run_bootstrap(
    *,
    force_browser: bool = False,
    force_config: bool = False,
    setup_postgres: bool = True,
    postgres_sql_file: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> BootstrapResult:
    """
    Download pinned **full-version** Chrome + ChromeDriver for this OS/arch into ``~/.slug/browser/...``.

    Default build is **143.0.7499.169** (Chrome + ChromeDriver from Google’s known-good list). Override with
    ``IGSCRAPER_CFT_FULL_VERSION``. Cache is reused only when ``.cft-pinned-version`` matches.

    If ``~/.slug/config.toml`` is missing, writes the bundled sample (unless *force_config*
    is used only when combined with ensure_sample — actually force_config overwrites config).
    """
    def _emit(msg: str) -> None:
        if progress:
            progress(msg)

    try:
        cft_platform = resolve_cft_platform()
    except OSError as e:
        return BootstrapResult(
            ok=False,
            message=str(e),
            cft_platform="",
            chrome_version="",
        )

    _emit(f"Resolved CFT platform: {cft_platform}")
    chrome_dir = get_chrome_extract_dir(cft_platform)
    driver_dir = get_chromedriver_extract_dir(cft_platform)
    chrome_bin = chrome_executable_path_after_extract(cft_platform, chrome_dir)
    driver_bin = chromedriver_executable_path_after_extract(cft_platform, driver_dir)
    _emit(f"Chrome cache dir: {chrome_dir}")
    _emit(f"ChromeDriver cache dir: {driver_dir}")

    full_version = _resolve_cft_full_version()
    _emit(f"Pinned CFT full version: {full_version} (override with IGSCRAPER_CFT_FULL_VERSION)")
    try:
        version, chrome_url, driver_url = _fetch_pinned_full_version_download_urls(
            cft_platform, full_version
        )
    except RuntimeError as e:
        return BootstrapResult(
            ok=False,
            message=str(e),
            cft_platform=cft_platform,
            chrome_version="",
        )

    pin_marker = _cft_pin_marker_path(cft_platform)
    cache_ok = (
        not force_browser
        and chrome_bin.is_file()
        and driver_bin.is_file()
        and pin_marker.is_file()
        and pin_marker.read_text(encoding="utf-8").strip() == version
    )

    if cache_ok:
        _emit(
            f"Cached Chrome + ChromeDriver match pinned version {version}; skipping downloads."
        )
        if sys.platform == "darwin":
            _apply_macos_cft_tree_fixes(chrome_dir, cft_platform)
            try_strip_quarantine_macos(chrome_bin)
            try_strip_quarantine_macos(driver_bin)
        if sys.platform.startswith("linux"):
            _apply_linux_cft_tree_chmod(chrome_dir, cft_platform)
        dotenv_path = _write_browser_env_to_cached_dotenv(chrome_bin, driver_bin)
        os.environ["CHROME_BIN"] = str(chrome_bin)
        os.environ["CHROMEDRIVER_BIN"] = str(driver_bin)
        _emit(f"Wrote browser env to {dotenv_path}")
        cfg_path, cfg_written = ensure_sample_config_in_cache(force=force_config)
        _emit(
            f"Sample config {'written' if cfg_written else 'already present'} at {cfg_path}"
        )
        pg_ok: Optional[bool] = None
        pg_msg = ""
        if setup_postgres:
            _emit("Running Postgres setup...")
            sql_text: Optional[str] = None
            sql_source = ""
            if postgres_sql_file:
                sql_path = Path(postgres_sql_file).expanduser().resolve()
                if not sql_path.is_file():
                    pg_ok, pg_msg = False, f"Postgres setup SQL file not found: {sql_path}"
                else:
                    sql_text = sql_path.read_text(encoding="utf-8")
                    sql_source = str(sql_path)
            else:
                sql_text, sql_source = _load_default_postgres_setup_sql()
                if sql_text is None:
                    pg_ok, pg_msg = False, f"Postgres setup SQL file not found: {sql_source}"

            if pg_ok is False:
                _emit(pg_msg)
                return BootstrapResult(
                    ok=False,
                    message=pg_msg,
                    cft_platform=cft_platform,
                    chrome_version=version,
                    chrome_bin=chrome_bin,
                    chromedriver_bin=driver_bin,
                    config_path=cfg_path,
                    config_written=cfg_written,
                    postgres_setup_attempted=True,
                    postgres_setup_ok=False,
                    postgres_message=pg_msg,
                )

            pg_ok, pg_msg = _run_postgres_setup(
                sql_text=sql_text or "",
                sql_source=sql_source,
                progress=progress,
            )
            _emit(pg_msg)
            if not pg_ok:
                return BootstrapResult(
                    ok=False,
                    message=pg_msg,
                    cft_platform=cft_platform,
                    chrome_version=version,
                    chrome_bin=chrome_bin,
                    chromedriver_bin=driver_bin,
                    config_path=cfg_path,
                    config_written=cfg_written,
                    postgres_setup_attempted=True,
                    postgres_setup_ok=False,
                    postgres_message=pg_msg,
                )

        return BootstrapResult(
            ok=True,
            message="Chrome and ChromeDriver already present in cache; skipped download.",
            cft_platform=cft_platform,
            chrome_version=version,
            chrome_bin=chrome_bin,
            chromedriver_bin=driver_bin,
            config_path=cfg_path,
            config_written=cfg_written,
            postgres_setup_attempted=setup_postgres,
            postgres_setup_ok=pg_ok,
            postgres_message=pg_msg,
        )

    _emit(f"Pinned Chrome for Testing version: {version}")
    _emit(f"Chrome zip URL: {chrome_url}")
    _emit(f"ChromeDriver zip URL: {driver_url}")

    get_slug_cache_dir().mkdir(parents=True, exist_ok=True)
    if force_browser:
        _emit("Force mode enabled; removing existing cached browser directories.")
        if chrome_dir.exists():
            shutil.rmtree(chrome_dir)
        if driver_dir.exists():
            shutil.rmtree(driver_dir)

    with tempfile.TemporaryDirectory(prefix="slug-cft-") as tmp:
        tdir = Path(tmp)
        c_zip = tdir / "chrome.zip"
        d_zip = tdir / "chromedriver.zip"
        try:
            _emit("Downloading Chrome zip...")
            _download_file(chrome_url, c_zip)
            _emit("Downloading ChromeDriver zip...")
            _download_file(driver_url, d_zip)
        except requests.RequestException as e:
            return BootstrapResult(
                ok=False,
                message=f"Download failed: {e}",
                cft_platform=cft_platform,
                chrome_version=version,
            )

        try:
            _emit("Extracting Chrome zip...")
            _extract_zip(c_zip, chrome_dir)
            _emit("Extracting ChromeDriver zip...")
            _extract_zip(d_zip, driver_dir)
        except zipfile.BadZipFile as e:
            return BootstrapResult(
                ok=False,
                message=f"Invalid zip from Chrome for Testing: {e}",
                cft_platform=cft_platform,
                chrome_version=version,
            )

    _chmod_plus_x(chrome_bin)
    _chmod_plus_x(driver_bin)
    if sys.platform == "darwin":
        _apply_macos_cft_tree_fixes(chrome_dir, cft_platform)
        try_strip_quarantine_macos(chrome_bin)
        try_strip_quarantine_macos(driver_bin)
    if sys.platform.startswith("linux"):
        _apply_linux_cft_tree_chmod(chrome_dir, cft_platform)
    dotenv_path = _write_browser_env_to_cached_dotenv(chrome_bin, driver_bin)
    os.environ["CHROME_BIN"] = str(chrome_bin)
    os.environ["CHROMEDRIVER_BIN"] = str(driver_bin)
    _emit(f"Wrote browser env to {dotenv_path}")
    _emit("Ensured executable permissions on browser binaries.")

    if not chrome_bin.is_file() or not driver_bin.is_file():
        return BootstrapResult(
            ok=False,
            message=(
                f"Extracted archives but binaries not found at:\n"
                f"  {chrome_bin}\n  {driver_bin}"
            ),
            cft_platform=cft_platform,
            chrome_version=version,
        )

    pin_marker.parent.mkdir(parents=True, exist_ok=True)
    pin_marker.write_text(version, encoding="utf-8")
    _emit(f"Recorded pinned version in {pin_marker}")

    cfg_path, cfg_written = ensure_sample_config_in_cache(force=force_config)
    _emit(f"Sample config {'written' if cfg_written else 'already present'} at {cfg_path}")
    _emit("Bootstrap finished successfully.")

    pg_ok: Optional[bool] = None
    pg_msg = ""
    if setup_postgres:
        _emit("Running Postgres setup...")
        sql_text: Optional[str] = None
        sql_source = ""
        if postgres_sql_file:
            sql_path = Path(postgres_sql_file).expanduser().resolve()
            if not sql_path.is_file():
                pg_ok, pg_msg = False, f"Postgres setup SQL file not found: {sql_path}"
            else:
                sql_text = sql_path.read_text(encoding="utf-8")
                sql_source = str(sql_path)
        else:
            sql_text, sql_source = _load_default_postgres_setup_sql()
            if sql_text is None:
                pg_ok, pg_msg = False, f"Postgres setup SQL file not found: {sql_source}"

        if pg_ok is False:
            _emit(pg_msg)
            return BootstrapResult(
                ok=False,
                message=pg_msg,
                cft_platform=cft_platform,
                chrome_version=version,
                chrome_bin=chrome_bin,
                chromedriver_bin=driver_bin,
                config_path=cfg_path,
                config_written=cfg_written,
                postgres_setup_attempted=True,
                postgres_setup_ok=False,
                postgres_message=pg_msg,
            )

        pg_ok, pg_msg = _run_postgres_setup(
            sql_text=sql_text or "",
            sql_source=sql_source,
            progress=progress,
        )
        _emit(pg_msg)
        if not pg_ok:
            return BootstrapResult(
                ok=False,
                message=pg_msg,
                cft_platform=cft_platform,
                chrome_version=version,
                chrome_bin=chrome_bin,
                chromedriver_bin=driver_bin,
                config_path=cfg_path,
                config_written=cfg_written,
                postgres_setup_attempted=True,
                postgres_setup_ok=False,
                postgres_message=pg_msg,
            )

    return BootstrapResult(
        ok=True,
        message="Bootstrap complete.",
        cft_platform=cft_platform,
        chrome_version=version,
        chrome_bin=chrome_bin,
        chromedriver_bin=driver_bin,
        config_path=cfg_path,
        config_written=cfg_written,
        postgres_setup_attempted=setup_postgres,
        postgres_setup_ok=pg_ok,
        postgres_message=pg_msg,
    )
