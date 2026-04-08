"""Chrome user-data paths for cookie capture."""
from __future__ import annotations

from igscraper.paths import get_cookie_capture_chrome_user_data_dir


def test_cookie_capture_user_data_dir_sanitizes_username(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/slug-test-home")
    p = get_cookie_capture_chrome_user_data_dir("user.name!")
    assert p.parts[-4:] == (".slug", "chrome-user-data", "save-cookie", "user.name")


def test_cookie_capture_user_data_dir_default_for_empty(monkeypatch):
    monkeypatch.setenv("HOME", "/tmp/slug-test-home")
    p = get_cookie_capture_chrome_user_data_dir("   ")
    assert p.name == "default"
