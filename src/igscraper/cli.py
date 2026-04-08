"""
Command-line interface for Slug-Ig-Crawler.

This script serves as the main entry point for running the scraper from the
command line. It handles parsing command-line arguments and initiating the
scraping pipeline.

Commands:
  run (default)     Run the pipeline; ``--config`` optional if ``~/.slug/config.toml`` exists.
  bootstrap       Download stable Chrome + ChromeDriver into ``~/.slug`` and install sample config.
  show-config     Print bundled sample TOML plus cached config/cookie paths.
  save-cookie     Capture Instagram login cookies into ``~/.slug/cookies``.
  list-cookies    Print only cached cookie JSON paths.
  version         Print installed package version.
"""
from __future__ import annotations

import argparse
import os
import sys
import toml
import psycopg
from dotenv import dotenv_values

# macOS: set before importing packages that may start threads (reduces Chrome fork crashes
# under embedded terminals / IDEs when launching Chrome for Testing).
if sys.platform == "darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

from difflib import get_close_matches
from pathlib import Path

# When running from a source checkout (`src/igscraper/...`), add `src/` so imports work.
# When installed as a wheel, site-packages already provides `igscraper`.
_pkg_dir = Path(__file__).resolve().parent
_src = _pkg_dir.parent
if _src.name == "src" and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from igscraper.bootstrap import read_bundled_sample_config_text, run_bootstrap
from igscraper.chrome_versions import try_version_line
from igscraper import __version__
from igscraper.login_Save_cookie import capture_login_cookies
from igscraper.paths import (
    CACHED_CONFIG_FILENAME,
    chrome_executable_path_after_extract,
    chromedriver_executable_path_after_extract,
    get_cached_browser_binaries,
    get_cached_config_path,
    get_cached_dotenv_path,
    get_chrome_extract_dir,
    get_chromedriver_extract_dir,
    get_cookie_cache_dir,
    get_slug_cache_dir,
    resolve_cft_platform,
    slug_cache_has_valid_browser_pair,
)
from igscraper.pg_env import (
    DEFAULT_PG_DATABASE,
    default_pg_user_when_unset,
    load_dotenv_for_app,
)


def _resolve_config_path(explicit: str | None) -> str:
    """Prefer explicit path, then ``~/.slug/config.toml`` if it exists."""
    if explicit:
        p = Path(explicit).expanduser()
        if not p.is_file():
            raise SystemExit(f"Config file not found: {p}")
        return str(p.resolve())
    cached = get_cached_config_path()
    if cached.is_file():
        return str(cached.resolve())
    raise SystemExit(
        "No config file specified and ~/.slug/config.toml not found.\n"
        "  Pass --config PATH, or run: Slug-Ig-Crawler bootstrap\n"
        "  (installs sample config to ~/.slug/config.toml), then edit cookies and settings."
    )


def _print_browser_binary_paths_first() -> None:
    """Print Chrome + ChromeDriver paths and ``--version`` lines first."""
    def _path_and_ver(label: str, path_str: str) -> None:
        print(f"  {label}")
        print(f"    {path_str}")
        v = try_version_line(path_str)
        if v:
            print(f"    {v}")
        else:
            print("    (version: binary missing or `--version` failed)")

    chrome_e = (os.environ.get("CHROME_BIN") or "").strip()
    driver_e = (os.environ.get("CHROMEDRIVER_BIN") or "").strip()
    print("Chrome / ChromeDriver:")
    if chrome_e:
        print("  CHROME_BIN")
        print(f"    {chrome_e}")
        v = try_version_line(chrome_e)
        if v:
            print(f"    {v}")
        else:
            print("    (version: not available)")
    if driver_e:
        print("  CHROMEDRIVER_BIN")
        print(f"    {driver_e}")
        v = try_version_line(driver_e)
        if v:
            print(f"    {v}")
        else:
            print("    (version: not available)")
    if chrome_e or driver_e:
        if bool(chrome_e) != bool(driver_e):
            print(
                "  (set both CHROME_BIN and CHROMEDRIVER_BIN, or unset both for ~/.slug/browser/)"
            )
        print()
        return

    c_cached, d_cached = get_cached_browser_binaries()
    if c_cached and d_cached:
        _path_and_ver("Chrome (cache)", str(c_cached))
        _path_and_ver("ChromeDriver (cache)", str(d_cached))
        print()
        return

    try:
        plat = resolve_cft_platform()
        c_root = get_chrome_extract_dir(plat)
        d_root = get_chromedriver_extract_dir(plat)
        c_exp = chrome_executable_path_after_extract(plat, c_root)
        d_exp = chromedriver_executable_path_after_extract(plat, d_root)
    except OSError:
        print("  (could not resolve platform-specific paths)")
        print()
        return
    _path_and_ver("Chrome (expected after bootstrap)", str(c_exp))
    _path_and_ver("ChromeDriver (expected after bootstrap)", str(d_exp))
    print()


def _maybe_warn_browser_cache() -> None:
    """If no explicit env override and no cached pair, stderr hint (suppressible)."""
    if os.environ.get("IGSCRAPER_SILENT_BROWSER_CACHE_WARN", "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return
    if os.environ.get("CHROME_BIN") or os.environ.get("CHROMEDRIVER_BIN"):
        return
    if slug_cache_has_valid_browser_pair():
        return
    print(
        "Slug-Ig-Crawler: no Chrome/ChromeDriver in ~/.slug/browser/ and CHROME_BIN/CHROMEDRIVER_BIN unset.\n"
        "  For a matching stable pair, run: Slug-Ig-Crawler bootstrap\n"
        "  (cache: ~/.slug). Silence this message: IGSCRAPER_SILENT_BROWSER_CACHE_WARN=1\n",
        file=sys.stderr,
    )


def _cmd_run(args: argparse.Namespace) -> None:
    def _apply_cached_pg_env_defaults() -> None:
        """
        Apply PUGSY_* vars from ~/.slug/.env as authoritative runtime defaults.
        """
        cache_env = get_cached_dotenv_path()
        if not cache_env.is_file():
            return
        vals = dotenv_values(str(cache_env))
        for key in (
            "PUGSY_PG_HOST",
            "PUGSY_PG_PORT",
            "PUGSY_PG_USER",
            "PUGSY_PG_PASSWORD",
            "PUGSY_PG_DATABASE",
        ):
            val = vals.get(key)
            if val is not None:
                os.environ[key] = str(val)

    def _preflight_postgres_ready() -> None:
        """
        Lightweight startup check: DB reachable and required ingestion tables exist.
        """
        _apply_cached_pg_env_defaults()
        load_dotenv_for_app()
        host = (os.environ.get("PUGSY_PG_HOST") or "localhost").strip()
        port = int((os.environ.get("PUGSY_PG_PORT") or "5432").strip())
        raw_user = (os.environ.get("PUGSY_PG_USER") or "").strip()
        user = raw_user if raw_user else default_pg_user_when_unset()
        password = os.environ.get("PUGSY_PG_PASSWORD") or ""
        database = (os.environ.get("PUGSY_PG_DATABASE") or "").strip() or DEFAULT_PG_DATABASE

        dsn = (
            f"host={host} port={port} dbname={database} "
            f"user={user} password={password} connect_timeout=5"
        )
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT to_regclass('public.crawled_posts'), "
                        "to_regclass('public.crawled_comments')"
                    )
                    posts_tbl, comments_tbl = cur.fetchone()
        except Exception as e:
            raise SystemExit(
                "Postgres preflight failed before pipeline start.\n"
                f"  target: host={host} port={port} db={database} user={user}\n"
                f"  error: {e}\n"
                "  Hint: run `Slug-Ig-Crawler bootstrap --setup-postgres` "
                "or fix ~/.slug/.env PUGSY_PG_* values."
            ) from e

        if not posts_tbl or not comments_tbl:
            raise SystemExit(
                "Postgres preflight failed: required tables missing.\n"
                f"  crawled_posts={posts_tbl!r}, crawled_comments={comments_tbl!r}\n"
                "  Run: `Slug-Ig-Crawler bootstrap --setup-postgres`."
            )

    config_path = _resolve_config_path(args.config)
    _maybe_warn_browser_cache()
    _preflight_postgres_ready()
    # Import only after env preflight to avoid import-time side effects altering PUGSY_* vars.
    from igscraper.pipeline import Pipeline
    pipeline = Pipeline(config_path=config_path)
    pipeline.run()


def _cmd_bootstrap(args: argparse.Namespace) -> None:
    _print_browser_binary_paths_first()
    print("Starting bootstrap...")
    print(f"  Cache root: {get_slug_cache_dir()}")
    print(f"  Config path: {get_cached_config_path()}")
    print(f"  Force browser download: {bool(args.force)}")
    print(f"  Force config overwrite: {bool(args.force_config)}")
    print(f"  Setup Postgres tables: {bool(args.setup_postgres)}")
    if args.postgres_sql_file:
        print(f"  Postgres SQL file override: {args.postgres_sql_file}")

    res = run_bootstrap(
        force_browser=args.force,
        force_config=args.force_config,
        setup_postgres=args.setup_postgres,
        postgres_sql_file=args.postgres_sql_file,
        progress=lambda msg: print(f"  - {msg}"),
    )
    if not res.ok:
        raise SystemExit(res.message)
    print(res.message)
    print(f"  Platform (Chrome for Testing): {res.cft_platform}")
    print(f"  Chrome version: {res.chrome_version}")
    if res.chrome_bin:
        print(f"  Chrome:       {res.chrome_bin}")
    if res.chromedriver_bin:
        print(f"  ChromeDriver: {res.chromedriver_bin}")
    if res.config_path:
        print(f"  Sample config: {res.config_path}" + (" (written)" if res.config_written else " (already existed)"))
    if res.postgres_setup_attempted:
        status = "ok" if res.postgres_setup_ok else "failed"
        print(f"  Postgres setup: {status}")
        if res.postgres_message:
            print(f"  Postgres details: {res.postgres_message}")


def _cmd_show_config(_args: argparse.Namespace) -> None:
    _print_browser_binary_paths_first()
    cached = get_cached_config_path()
    print("=== Bundled sample config (config.example.toml) ===\n")
    print(read_bundled_sample_config_text().rstrip() + "\n")
    print("=== User cache ===\n")
    print(f"  ~/.slug             : {get_slug_cache_dir()}")
    print(f"  ~/.slug/config.toml : {cached}")
    print(f"  exists: {cached.is_file()}")
    if cached.is_file():
        print(f"  resolved: {cached.resolve()}")
    config_files = _list_cache_config_paths()
    print(f"\n  cached config files ({len(config_files)}):")
    for p in config_files:
        print(f"    - {p}")

    cookie_files = _list_cookie_paths()
    print(f"\n  cached cookie files ({len(cookie_files)}):")
    for p in cookie_files:
        print(f"    - {p}")


def _list_cache_config_paths() -> list[Path]:
    """Return absolute paths to TOML files under ~/.slug."""
    root = get_slug_cache_dir()
    if not root.is_dir():
        return []
    return sorted(
        [p.resolve() for p in root.glob("**/*.toml") if p.is_file()],
        key=lambda p: str(p),
    )


def _list_cookie_paths() -> list[Path]:
    """Return absolute paths to cookie JSON files under ~/.slug/cookies."""
    cookie_dir = get_cookie_cache_dir()
    if not cookie_dir.is_dir():
        return []
    return sorted(
        [p.resolve() for p in cookie_dir.glob("*.json") if p.is_file()],
        key=lambda p: str(p),
    )


def _cmd_save_cookie(args: argparse.Namespace) -> None:
    def _update_cached_config_cookie_file_abs(latest_cookie_path: Path) -> None:
        cfg = get_cached_config_path()
        if not cfg.is_file():
            return
        try:
            data = toml.load(str(cfg))
            data_section = data.get("data")
            if not isinstance(data_section, dict):
                return
            data_section["cookie_file"] = str(latest_cookie_path.resolve())
            cfg.write_text(toml.dumps(data), encoding="utf-8")
            print(f"  Updated config cookie_file: {data_section['cookie_file']}")
        except Exception:
            # Keep save-cookie robust; capture result is still valid even if config update fails.
            return

    _print_browser_binary_paths_first()
    result = capture_login_cookies(args.username)
    _update_cached_config_cookie_file_abs(result.latest_path)
    print("Cookie capture complete.")
    print(f"  Username:        {result.username}")
    print(f"  Browser version: {result.browser_version}")
    print(f"  Cookie count:    {result.cookie_count}")
    print(f"  Cookie file:     {result.cookie_path}")
    print(f"  Latest pointer:  {result.latest_path}")


def _cmd_list_cookies(_args: argparse.Namespace) -> None:
    for p in _list_cookie_paths():
        print(str(p))


def _cmd_version(_args: argparse.Namespace) -> None:
    print(__version__)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="Slug-Ig-Crawler",
        description=(
            "Slug-Ig-Crawler CLI\n\n"
            "Use one of the commands below. For command-specific help:\n"
            "  Slug-Ig-Crawler <command> --help"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run pipeline", description="Run pipeline.")
    run_p.add_argument(
        "--config",
        default=None,
        help=(
            "Path to config TOML. If omitted, uses ~/.slug/config.toml when that file exists "
            f"(default path: ~/.slug/{CACHED_CONFIG_FILENAME})."
        ),
    )

    b = sub.add_parser(
        "bootstrap",
        help="Download browser/cache sample config",
        description="Bootstrap Chrome + ChromeDriver cache and sample config.",
    )
    b.add_argument(
        "--force",
        action="store_true",
        help="Re-download Chrome/ChromeDriver even if cache exists.",
    )
    b.add_argument(
        "--force-config",
        action="store_true",
        help="Overwrite ~/.slug/config.toml with the bundled sample.",
    )
    b.add_argument(
        "--setup-postgres",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Run postgres table/index setup using bundled postgres_setup.sql. "
            "Uses local defaults when PUGSY_PG_* are unset (host localhost, port 5432, "
            "database postgres; on macOS user defaults to your login when unset). "
            "On success writes ~/.slug/.env. "
            "Use --no-setup-postgres to skip."
        ),
    )
    b.add_argument(
        "--postgres-sql-file",
        default=None,
        help="Optional path override for postgres setup SQL file.",
    )

    sub.add_parser(
        "show-config",
        help="Show bundled and cached config details",
        description="Show bundled sample config plus cache paths and discovered files.",
    )

    sc = sub.add_parser(
        "save-cookie",
        help="Capture Instagram login cookies",
        description="Capture login cookies and save into ~/.slug/cookies.",
    )
    sc.add_argument(
        "--username",
        required=True,
        help="Instagram username for naming the saved cookie file.",
    )

    sub.add_parser(
        "list-cookies",
        help="List cached cookie JSON files",
        description="Print only cookie JSON paths from ~/.slug/cookies.",
    )
    sub.add_parser("version", help="Print package version", description="Print package version.")
    return p


def main() -> None:
    argv = sys.argv[1:]
    parser = _build_parser()
    known_cmds = ("run", "bootstrap", "show-config", "save-cookie", "list-cookies", "version")

    if not argv:
        parser.print_help()
        return

    if argv[0] in ("-h", "--help"):
        parser.print_help()
        return

    # Backward compatibility: `Slug-Ig-Crawler --config ...` means `run --config ...`
    if argv[0].startswith("-"):
        argv = ["run", *argv]

    if argv[0] not in known_cmds:
        suggestion = get_close_matches(argv[0], known_cmds, n=1)
        hint = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
        parser.exit(
            2,
            f"error: invalid command '{argv[0]}'.{hint}\nUse 'Slug-Ig-Crawler --help' to see commands.\n",
        )

    args = parser.parse_args(argv)
    if args.command == "run":
        _cmd_run(args)
    elif args.command == "bootstrap":
        _cmd_bootstrap(args)
    elif args.command == "show-config":
        _cmd_show_config(args)
    elif args.command == "save-cookie":
        _cmd_save_cookie(args)
    elif args.command == "list-cookies":
        _cmd_list_cookies(args)
    elif args.command == "version":
        _cmd_version(args)


if __name__ == "__main__":
    main()
