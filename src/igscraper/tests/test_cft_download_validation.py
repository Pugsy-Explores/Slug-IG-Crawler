"""Chrome for Testing download URL validation (platform vs URL path)."""
from __future__ import annotations

import pytest

from igscraper.bootstrap import validate_cft_download_urls_for_platform


def test_validate_urls_mac_arm64_ok():
    validate_cft_download_urls_for_platform(
        "mac-arm64",
        "https://storage.googleapis.com/chrome-for-testing-public/143.0.0.0/mac-arm64/chrome-mac-arm64.zip",
        "https://storage.googleapis.com/chrome-for-testing-public/143.0.0.0/mac-arm64/chromedriver-mac-arm64.zip",
    )


def test_validate_urls_linux64_ok():
    validate_cft_download_urls_for_platform(
        "linux64",
        "https://storage.googleapis.com/chrome-for-testing-public/143.0.0.0/linux64/chrome-linux64.zip",
        "https://storage.googleapis.com/chrome-for-testing-public/143.0.0.0/linux64/chromedriver-linux64.zip",
    )


def test_validate_urls_rejects_http():
    with pytest.raises(RuntimeError, match="https"):
        validate_cft_download_urls_for_platform(
            "mac-arm64",
            "http://example.com/mac-arm64/chrome-mac-arm64.zip",
            "https://storage.googleapis.com/x/mac-arm64/chromedriver-mac-arm64.zip",
        )


def test_validate_urls_rejects_wrong_segment():
    with pytest.raises(RuntimeError, match="platform mismatch"):
        validate_cft_download_urls_for_platform(
            "mac-arm64",
            "https://storage.googleapis.com/x/linux64/chrome-linux64.zip",
            "https://storage.googleapis.com/x/mac-arm64/chromedriver-mac-arm64.zip",
        )


def test_describe_cft_host():
    from igscraper.paths import describe_cft_host

    s = describe_cft_host()
    assert "/" in s
