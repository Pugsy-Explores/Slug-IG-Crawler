"""Tests for postgres_local_install helpers and install script presence."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from igscraper import postgres_local_install as pli


def test_detect_linux_family_debian_via_debian_version(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (tmp_path / "etc").mkdir(parents=True)
    (tmp_path / "etc/debian_version").write_text("12.0\n", encoding="utf-8")
    assert pli.detect_linux_family(root=tmp_path) == "debian"


def test_detect_linux_family_debian_via_os_release(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (tmp_path / "etc").mkdir(parents=True)
    (tmp_path / "etc/os-release").write_text(
        'ID=ubuntu\nVERSION_ID="22.04"\n',
        encoding="utf-8",
    )
    assert pli.detect_linux_family(root=tmp_path) == "debian"


def test_detect_linux_family_rhel_via_os_release(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (tmp_path / "etc").mkdir(parents=True)
    (tmp_path / "etc/os-release").write_text(
        'ID="fedora"\nVERSION_ID=40\n',
        encoding="utf-8",
    )
    assert pli.detect_linux_family(root=tmp_path) == "rhel"


def test_detect_linux_family_rhel_via_redhat_release(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (tmp_path / "etc").mkdir(parents=True)
    (tmp_path / "etc/redhat-release").write_text("Rocky Linux release 9\n", encoding="utf-8")
    assert pli.detect_linux_family(root=tmp_path) == "rhel"


def test_detect_linux_family_unknown_empty_etc(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    (tmp_path / "etc").mkdir(parents=True)
    assert pli.detect_linux_family(root=tmp_path) == "unknown"


def test_detect_linux_family_unknown_non_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert pli.detect_linux_family(root=Path("/")) == "unknown"


def test_parse_os_release():
    text = 'FOO="bar baz"\nID=debian\n'
    d = pli._parse_os_release(text)
    assert d["id"] == "debian"
    assert d["foo"] == "bar baz"


def test_has_psql_monkeypatch(monkeypatch):
    monkeypatch.setattr(pli.shutil, "which", lambda _: None)
    assert pli.has_psql() is False
    monkeypatch.setattr(pli.shutil, "which", lambda _: "/usr/bin/psql")
    assert pli.has_psql() is True


def test_install_postgres_script_exists_and_bash_syntax():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "install_postgres_local.sh"
    assert script.is_file(), f"expected {script}"
    r = subprocess.run(
        ["bash", "-n", str(script)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stderr


def test_install_script_hint_non_empty():
    assert "install_postgres_local" in pli.install_script_hint()
