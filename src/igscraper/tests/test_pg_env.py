"""Tests for local Postgres defaults and ~/.slug/.env helpers."""
from __future__ import annotations

import os

import igscraper.pg_env as pg_env_mod

from igscraper.pg_env import (
    DEFAULT_PG_DATABASE,
    DEFAULT_PG_PORT,
    ResolvedPgEnv,
    apply_resolved_to_environ,
    resolve_pg_env_for_bootstrap,
    write_cached_dotenv,
)


def test_resolve_default_port_when_unset(monkeypatch):
    monkeypatch.delenv("PUGSY_PG_PORT", raising=False)
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    assert r.port == DEFAULT_PG_PORT == 5432


def test_default_user_darwin_uses_getuser(monkeypatch):
    monkeypatch.delenv("PUGSY_PG_USER", raising=False)
    monkeypatch.setattr(pg_env_mod.sys, "platform", "darwin")
    monkeypatch.setattr(pg_env_mod.getpass, "getuser", lambda: "alice")
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    assert r.user == "alice"


def test_default_user_linux_uses_postgres(monkeypatch):
    monkeypatch.delenv("PUGSY_PG_USER", raising=False)
    monkeypatch.setattr(pg_env_mod.sys, "platform", "linux")
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    assert r.user == "postgres"


def test_resolve_uses_default_database_when_unset(monkeypatch):
    monkeypatch.delenv("PUGSY_PG_DATABASE", raising=False)
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    assert r.database == DEFAULT_PG_DATABASE
    assert r.used_default_database is True


def test_resolve_respects_explicit_database(monkeypatch):
    monkeypatch.setenv("PUGSY_PG_DATABASE", "mydb")
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    assert r.database == "mydb"
    assert r.used_default_database is False


def test_write_cached_dotenv_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    resolved = ResolvedPgEnv(
        host="h",
        port=5432,
        user="u",
        password="p",
        database="d",
        used_default_database=False,
    )
    path = write_cached_dotenv(resolved)
    assert path.name == ".env"
    text = path.read_text(encoding="utf-8")
    assert "PUGSY_PG_HOST=h" in text
    assert "PUGSY_PG_DATABASE=d" in text


def test_apply_resolved_to_environ(monkeypatch):
    monkeypatch.delenv("PUGSY_PG_DATABASE", raising=False)
    r = resolve_pg_env_for_bootstrap(apply_default_database=True)
    apply_resolved_to_environ(r)
    assert os.environ["PUGSY_PG_DATABASE"] == DEFAULT_PG_DATABASE
