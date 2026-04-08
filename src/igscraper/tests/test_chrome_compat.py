"""chrome_compat helpers."""
from __future__ import annotations

from unittest.mock import patch

from selenium.webdriver.chrome.options import Options

from igscraper.chrome_compat import (
    MACOS_GOOGLE_CHROME_BIN,
    apply_automation_compat_flags,
    macos_google_chrome_binary_if_present,
)


def test_macos_google_chrome_binary_if_present_missing():
    with patch("igscraper.chrome_compat.Path.is_file", return_value=False):
        with patch("igscraper.chrome_compat.sys.platform", "darwin"):
            assert macos_google_chrome_binary_if_present() is None


def test_macos_google_chrome_binary_if_present_non_darwin():
    with patch("igscraper.chrome_compat.sys.platform", "linux"):
        assert macos_google_chrome_binary_if_present() is None


def test_apply_automation_compat_flags_headless():
    o = Options()
    apply_automation_compat_flags(o, headless=True)
    args = o.arguments
    assert "--no-sandbox" in args
    assert "--disable-dev-shm-usage" in args
    assert "--disable-gpu" in args
    assert "--start-maximized" not in args


def test_apply_automation_compat_flags_visible():
    o = Options()
    apply_automation_compat_flags(o, headless=False)
    args = o.arguments
    assert "--start-maximized" in args


def test_macos_path_constant():
    assert "Google Chrome.app" in MACOS_GOOGLE_CHROME_BIN
