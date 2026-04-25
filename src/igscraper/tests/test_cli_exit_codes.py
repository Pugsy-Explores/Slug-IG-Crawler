from __future__ import annotations

import sys
import types

import pytest

import igscraper.cli as cli


class _DummyCursor:
    def execute(self, *_args, **_kwargs) -> None:
        return None

    def fetchone(self):
        return ("public.crawled_posts", "public.crawled_comments")

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None


class _DummyConn:
    def cursor(self):
        return _DummyCursor()

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        return None


def _set_run_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["Slug-Ig-Crawler", "run", "--config", "dummy.toml"])


def test_main_run_happy_path_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_run_argv(monkeypatch)
    monkeypatch.setattr(cli, "_resolve_config_path", lambda _p: "dummy.toml")
    monkeypatch.setattr(cli, "_maybe_warn_browser_cache", lambda: None)
    monkeypatch.setattr(cli, "load_dotenv_for_app", lambda: None)
    monkeypatch.setattr(cli.psycopg, "connect", lambda _dsn: _DummyConn())

    fake_pipeline_module = types.ModuleType("igscraper.pipeline")

    class _Pipeline:
        def __init__(self, config_path: str):
            assert config_path == "dummy.toml"

        def run(self) -> dict:
            return {"ok": True}

    fake_pipeline_module.Pipeline = _Pipeline
    monkeypatch.setitem(sys.modules, "igscraper.pipeline", fake_pipeline_module)

    assert cli.main() == 0


def test_main_run_pipeline_exception_returns_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_run_argv(monkeypatch)
    monkeypatch.setattr(cli, "_resolve_config_path", lambda _p: "dummy.toml")
    monkeypatch.setattr(cli, "_maybe_warn_browser_cache", lambda: None)
    monkeypatch.setattr(cli, "load_dotenv_for_app", lambda: None)
    monkeypatch.setattr(cli.psycopg, "connect", lambda _dsn: _DummyConn())

    fake_pipeline_module = types.ModuleType("igscraper.pipeline")

    class _Pipeline:
        def __init__(self, config_path: str):
            assert config_path == "dummy.toml"

        def run(self) -> dict:
            raise RuntimeError("boom")

    fake_pipeline_module.Pipeline = _Pipeline
    monkeypatch.setitem(sys.modules, "igscraper.pipeline", fake_pipeline_module)

    assert cli.main() == 1


def test_main_run_db_preflight_failure_is_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_run_argv(monkeypatch)
    monkeypatch.setattr(cli, "_resolve_config_path", lambda _p: "dummy.toml")
    monkeypatch.setattr(cli, "_maybe_warn_browser_cache", lambda: None)
    monkeypatch.setattr(cli, "load_dotenv_for_app", lambda: None)

    def _raise_connect(_dsn: str):
        raise RuntimeError("db down")

    monkeypatch.setattr(cli.psycopg, "connect", _raise_connect)

    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code != 0


def test_main_unexpected_exception_returns_non_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["Slug-Ig-Crawler", "version"])
    monkeypatch.setattr(cli, "_cmd_version", lambda _args: (_ for _ in ()).throw(RuntimeError("unexpected")))

    assert cli.main() == 1
