"""
Local Postgres defaults and ``~/.slug/.env`` persistence.

Bootstrap and ``FileEnqueuer`` share the same defaults so a first-time local run
does not fail on an empty ``PUGSY_PG_DATABASE``. On macOS, when ``PUGSY_PG_USER`` is
unset, the default login matches typical Homebrew Postgres. Production must still set
explicit credentials (and usually a non-default database name).
"""
from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from igscraper.paths import get_cached_dotenv_path, get_slug_cache_dir

# Native Postgres default port is 5432. Use PUGSY_PG_PORT=5433 if you map Docker that way.
DEFAULT_PG_HOST = "localhost"
DEFAULT_PG_PORT = 5432
DEFAULT_PG_USER = "postgres"
DEFAULT_PG_PASSWORD = ""
DEFAULT_PG_DATABASE = "postgres"


def default_pg_user_when_unset() -> str:
    """
    When ``PUGSY_PG_USER`` is unset or blank.

    Homebrew PostgreSQL on macOS typically creates a superuser matching the OS login, not
    ``postgres``. Linux packages and Docker images usually expose ``postgres``.
    """
    if sys.platform == "darwin":
        try:
            return getpass.getuser()
        except Exception:
            return DEFAULT_PG_USER
    return DEFAULT_PG_USER


@dataclass(frozen=True)
class ResolvedPgEnv:
    host: str
    port: int
    user: str
    password: str
    database: str
    used_default_database: bool


def resolve_pg_env_for_bootstrap(*, apply_default_database: bool) -> ResolvedPgEnv:
    """
    Read ``PUGSY_PG_*`` from the environment with the same fallbacks as bootstrap.

    When *apply_default_database* is true and ``PUGSY_PG_DATABASE`` is unset or
    blank, use :data:`DEFAULT_PG_DATABASE` (``postgres``).
    """
    host = (os.environ.get("PUGSY_PG_HOST") or DEFAULT_PG_HOST).strip()
    port = int((os.environ.get("PUGSY_PG_PORT") or str(DEFAULT_PG_PORT)).strip())
    raw_user = (os.environ.get("PUGSY_PG_USER") or "").strip()
    user = raw_user if raw_user else default_pg_user_when_unset()
    password = os.environ.get("PUGSY_PG_PASSWORD") or ""
    database = (os.environ.get("PUGSY_PG_DATABASE") or "").strip()
    used_default = False
    if not database and apply_default_database:
        database = DEFAULT_PG_DATABASE
        used_default = True
    return ResolvedPgEnv(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        used_default_database=used_default,
    )


def write_cached_dotenv(resolved: ResolvedPgEnv) -> Path:
    """
    Write ``~/.slug/.env`` with the effective connection values.

    Called after a successful ``bootstrap`` Postgres setup so later processes
    and ``FileEnqueuer`` pick up the same DSN without extra shell wiring.
    """
    path = get_cached_dotenv_path()
    get_slug_cache_dir().mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if path.is_file():
        existing = path.read_text(encoding="utf-8").splitlines()

    kept: list[str] = []
    for line in existing:
        if line.startswith("PUGSY_PG_"):
            continue
        kept.append(line)

    if not kept:
        kept.append(
            "# Slug-Ig-Crawler — Postgres (local defaults). Override via shell env or project .env."
        )
    if kept and kept[-1] != "":
        kept.append("")

    kept.extend(
        [
            f"PUGSY_PG_HOST={resolved.host}",
            f"PUGSY_PG_PORT={resolved.port}",
            f"PUGSY_PG_USER={resolved.user}",
            f"PUGSY_PG_PASSWORD={resolved.password}",
            f"PUGSY_PG_DATABASE={resolved.database}",
            "",
        ]
    )
    path.write_text("\n".join(kept), encoding="utf-8")
    return path


def apply_resolved_to_environ(resolved: ResolvedPgEnv) -> None:
    """Mirror resolved values into ``os.environ`` for the current process."""
    os.environ["PUGSY_PG_HOST"] = resolved.host
    os.environ["PUGSY_PG_PORT"] = str(resolved.port)
    os.environ["PUGSY_PG_USER"] = resolved.user
    os.environ["PUGSY_PG_PASSWORD"] = resolved.password
    os.environ["PUGSY_PG_DATABASE"] = resolved.database


def load_dotenv_for_app() -> None:
    """
    Load env files in precedence order:

    Priority (highest -> lowest):
    1. Existing exported process environment.
    2. ``~/.slug/.env`` cache file.
    3. ``ENV_FILE`` or ``.env`` in current working directory.
    """
    # Preserve values already in the process environment (typically shell-exported).
    preserved = dict(os.environ)

    cache_path = get_cached_dotenv_path()
    if cache_path.is_file():
        # Force cache values to win over any previously loaded project dotenv values.
        load_dotenv(dotenv_path=cache_path, override=True)
    project = os.environ.get("ENV_FILE", ".env")
    p = Path(project).expanduser()
    if p.is_file():
        load_dotenv(dotenv_path=str(p), override=False)

    # Restore pre-existing process environment values so explicit exports stay highest priority.
    for k, v in preserved.items():
        os.environ[k] = v
