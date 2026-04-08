"""Hints when Postgres bootstrap cannot connect."""
from __future__ import annotations

from igscraper.bootstrap import pg_connection_failure_hint, pg_role_missing_hint


def test_hint_empty_when_not_connection_refused():
    assert pg_connection_failure_hint(RuntimeError("auth failed")) == ""


def test_role_hint_for_missing_postgres_user():
    h = pg_role_missing_hint(RuntimeError('FATAL:  role "postgres" does not exist'))
    assert "Homebrew" in h


def test_hint_includes_skip_flag_for_connection_refused():
    h = pg_connection_failure_hint(
        RuntimeError(
            'connection failed: connection to server at "127.0.0.1", port 5432 failed: '
            "could not receive data from server: Connection refused"
        )
    )
    assert "Hint:" in h
    assert "--no-setup-postgres" in h
