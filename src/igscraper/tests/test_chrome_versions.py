"""Chrome / ChromeDriver four-part version assertion."""
from __future__ import annotations

import pytest

from igscraper.chrome_versions import assert_chrome_and_chromedriver_major_match, try_version_line


def test_quad_match_ok(monkeypatch):
    outputs = {
        "/fake/chrome": "Google Chrome 147.0.7727.56\n",
        "/fake/driver": "ChromeDriver 147.0.7727.56 (abc)\n",
    }

    def fake_check_output(cmd, **kwargs):
        return outputs[cmd[0]]

    monkeypatch.setattr("igscraper.chrome_versions.subprocess.check_output", fake_check_output)
    c, d, quad = assert_chrome_and_chromedriver_major_match("/fake/chrome", "/fake/driver")
    assert "147.0.7727.56" in c
    assert "147.0.7727.56" in d
    assert quad == "147.0.7727.56"


def test_quad_mismatch_raises(monkeypatch):
    outputs = {
        "/fake/chrome": "Google Chrome 146.0.1.2\n",
        "/fake/driver": "ChromeDriver 147.0.1.2\n",
    }

    def fake_check_output(cmd, **kwargs):
        return outputs[cmd[0]]

    monkeypatch.setattr("igscraper.chrome_versions.subprocess.check_output", fake_check_output)
    with pytest.raises(RuntimeError, match="four-part versions must match"):
        assert_chrome_and_chromedriver_major_match("/fake/chrome", "/fake/driver")


def test_same_major_different_patch_raises(monkeypatch):
    """Same major line; last segment must match (CFT pairs are build-locked)."""
    outputs = {
        "/fake/chrome": "Google Chrome for Testing 143.0.7499.169\n",
        "/fake/driver": "ChromeDriver 143.0.7499.192 (hash)\n",
    }

    def fake_check_output(cmd, **kwargs):
        return outputs[cmd[0]]

    monkeypatch.setattr("igscraper.chrome_versions.subprocess.check_output", fake_check_output)
    with pytest.raises(RuntimeError, match="four-part versions must match"):
        assert_chrome_and_chromedriver_major_match("/fake/chrome", "/fake/driver")


def test_try_version_line_missing_binary():
    assert try_version_line("/nonexistent/no-chrome") is None
