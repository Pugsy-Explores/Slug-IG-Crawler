"""CookieCaptureResult JSON helpers for subprocess worker."""
from __future__ import annotations

from pathlib import Path

from igscraper.login_Save_cookie import (
    CookieCaptureResult,
    _cookie_result_from_dict,
    _cookie_result_to_dict,
)


def test_cookie_result_roundtrip():
    r = CookieCaptureResult(
        username="u",
        browser_version="147",
        cookie_count=3,
        cookie_path=Path("/tmp/a.json"),
        latest_path=Path("/tmp/latest.json"),
    )
    d = _cookie_result_to_dict(r)
    r2 = _cookie_result_from_dict(d)
    assert r2 == r
